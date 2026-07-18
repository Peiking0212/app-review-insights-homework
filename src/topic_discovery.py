"""模型驱动的动态主题发现与确定性引用校验。"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from src.config import ModelConfig
from src.prompts import build_topic_messages
from src.schemas import Review, TopicDiscoveryResult


class TopicDiscoveryError(RuntimeError):
    """主题发现无法安全完成。"""


def prepare_reviews(records: Iterable[Mapping[str, Any]]) -> list[Review]:
    """把清洗记录转换为带稳定内部 ID 的 Review 对象。"""
    prepared: list[Review] = []
    used_ids: set[str] = set()

    for index, source_record in enumerate(records, start=1):
        record = dict(source_record)
        original_id = str(record.get("review_id") or "").strip()
        candidate = (
            original_id
            if re.fullmatch(r"REV-[A-Za-z0-9_-]+", original_id)
            else ""
        )
        if not candidate or candidate in used_ids:
            candidate = f"REV-{index:04d}"
            while candidate in used_ids:
                index += 1
                candidate = f"REV-{index:04d}"

        record["review_id"] = candidate
        record["source_id"] = str(record.get("source_id") or original_id or candidate)
        record["source"] = str(record.get("source") or "uploaded_file")
        record["storefront"] = str(record.get("storefront") or "us").lower()
        for optional_field in ("title", "version", "published_at"):
            value = record.get(optional_field)
            if value is None or (isinstance(value, float) and value != value):
                record[optional_field] = None
        record["title"] = str(record.get("title") or "")
        prepared.append(Review.model_validate(record))
        used_ids.add(candidate)

    return prepared


def validate_topic_references(
    result: TopicDiscoveryResult, valid_review_ids: set[str]
) -> None:
    """校验模型引用真实存在，并确保每条 Insight 只属于一个 Topic。"""
    errors: list[str] = []
    insight_by_id = {insight.insight_id: insight for insight in result.insights}

    invalid_insight_reviews = sorted(
        {
            insight.review_id
            for insight in result.insights
            if insight.review_id not in valid_review_ids
        }
    )
    invalid_other_reviews = sorted(set(result.other_review_ids) - valid_review_ids)
    if invalid_insight_reviews:
        errors.append("Insight 引用了不存在的评论：" + ", ".join(invalid_insight_reviews))
    if invalid_other_reviews:
        errors.append("OTHER 引用了不存在的评论：" + ", ".join(invalid_other_reviews))

    assigned_insight_ids: list[str] = []
    for topic in result.topics:
        missing_insights = sorted(set(topic.insight_ids) - set(insight_by_id))
        invalid_topic_reviews = sorted(
            set(topic.representative_review_ids) - valid_review_ids
        )
        linked_reviews = {
            insight_by_id[insight_id].review_id
            for insight_id in topic.insight_ids
            if insight_id in insight_by_id
        }
        unlinked_representatives = sorted(
            set(topic.representative_review_ids) - linked_reviews
        )
        if missing_insights:
            errors.append(
                f"{topic.topic_id} 引用了不存在的 Insight："
                + ", ".join(missing_insights)
            )
        if invalid_topic_reviews:
            errors.append(
                f"{topic.topic_id} 引用了不存在的评论："
                + ", ".join(invalid_topic_reviews)
            )
        if unlinked_representatives:
            errors.append(
                f"{topic.topic_id} 的代表评论不属于该主题："
                + ", ".join(unlinked_representatives)
            )
        assigned_insight_ids.extend(topic.insight_ids)

    assignment_counts = Counter(assigned_insight_ids)
    duplicated = sorted(
        insight_id for insight_id, count in assignment_counts.items() if count > 1
    )
    unassigned = sorted(set(insight_by_id) - set(assigned_insight_ids))
    if duplicated:
        errors.append("Insight 被分入多个 Topic：" + ", ".join(duplicated))
    if unassigned:
        errors.append("Insight 没有归入 Topic：" + ", ".join(unassigned))

    insight_review_ids = {insight.review_id for insight in result.insights}
    overlap = sorted(insight_review_ids & set(result.other_review_ids))
    unaccounted = sorted(
        valid_review_ids - insight_review_ids - set(result.other_review_ids)
    )
    if overlap:
        errors.append("评论同时进入 Topic 和 OTHER：" + ", ".join(overlap))
    if unaccounted:
        errors.append("评论既未提取 Insight 也未进入 OTHER：" + ", ".join(unaccounted))

    if errors:
        raise TopicDiscoveryError("；".join(errors))


class TopicDiscoveryService:
    """通过 OpenAI-compatible API 获取 Pydantic 校验后的主题结果。"""

    def __init__(self, config: ModelConfig | None = None) -> None:
        self.config = config or ModelConfig.from_env()

    def discover(
        self, reviews: Sequence[Review], analysis_goal: str
    ) -> TopicDiscoveryResult:
        if not reviews:
            raise TopicDiscoveryError("没有可用于主题发现的有效评论。")

        try:
            import instructor
            from openai import OpenAI

            openai_client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
            client = instructor.from_openai(openai_client)
            result = client.chat.completions.create(
                model=self.config.model,
                response_model=TopicDiscoveryResult,
                messages=build_topic_messages(reviews, analysis_goal),
                max_retries=1,
            )
        except TopicDiscoveryError:
            raise
        except Exception as error:
            raise TopicDiscoveryError(
                "模型调用或结构化输出失败，本阶段已停止。"
                f"请检查模型配置、网络和模型兼容性。错误类型：{type(error).__name__}"
            ) from error

        validate_topic_references(
            result, {review.review_id for review in reviews}
        )
        return result
