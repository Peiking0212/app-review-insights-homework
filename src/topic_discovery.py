"""分批提取 Atomic Insight、统一聚合 Topic 并确定性校验引用。"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

from src.config import ModelConfig
from src.prompts import (
    build_insight_extraction_messages,
    build_insight_repair_messages,
    build_topic_aggregation_messages,
    build_topic_repair_messages,
)
from src.schemas import (
    AtomicInsight,
    InsightExtractionBatch,
    Review,
    Topic,
    TopicAggregationDraft,
    TopicAggregationRepairDraft,
    TopicDiscoveryResult,
)


DEFAULT_INSIGHT_BATCH_SIZE = 20
MAX_REPRESENTATIVE_REVIEWS = 3


class TopicDiscoveryError(RuntimeError):
    """主题发现无法安全完成。"""


class IncompleteInsightBatchError(TopicDiscoveryError):
    """Insight 批次只有评论遗漏，可进入一次有限补提取。"""

    def __init__(self, missing_review_ids: Sequence[str]) -> None:
        self.missing_review_ids = list(missing_review_ids)
        super().__init__(
            "本批评论未被处理：" + ", ".join(self.missing_review_ids)
        )


class IncompleteTopicAggregationError(TopicDiscoveryError):
    """Topic 聚合只有 Insight 遗漏，可进入一次有限修复。"""

    def __init__(self, missing_insight_ids: Sequence[str]) -> None:
        self.missing_insight_ids = list(missing_insight_ids)
        super().__init__(
            "Insight 没有归入 Topic：" + ", ".join(self.missing_insight_ids)
        )


def _uses_deepseek(config: ModelConfig) -> bool:
    """识别 DeepSeek 官方接口或 DeepSeek 模型名称。"""
    hostname = urlparse(config.base_url or "").hostname or ""
    return hostname.endswith("deepseek.com") or config.model.startswith("deepseek-")


def build_model_request_options(config: ModelConfig) -> dict[str, Any]:
    """返回服务商特定参数，避免把兼容参数发送给其他模型服务。"""
    if _uses_deepseek(config):
        return {"extra_body": {"thinking": {"type": "disabled"}}}
    return {}


def safe_provider_error(error: Exception, api_key: str = "") -> str:
    """提取最底层错误并脱敏，供 UI 展示真实且安全的失败原因。"""
    root_error = error
    visited: set[int] = set()
    while root_error.__cause__ is not None and id(root_error) not in visited:
        visited.add(id(root_error))
        root_error = root_error.__cause__

    detail = str(root_error).strip() or type(root_error).__name__
    if api_key:
        detail = detail.replace(api_key, "[REDACTED]")
    detail = re.sub(r"Bearer\s+[^\s,}\]]+", "Bearer [REDACTED]", detail, flags=re.I)
    detail = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", detail)
    detail = " ".join(detail.split())
    if len(detail) > 500:
        detail = detail[:497] + "..."
    return f"{type(root_error).__name__}: {detail}"


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


def batch_reviews(
    reviews: Sequence[Review], batch_size: int = DEFAULT_INSIGHT_BATCH_SIZE
) -> list[list[Review]]:
    """按输入顺序稳定切分评论，避免单次提取请求过大。"""
    if batch_size < 1:
        raise TopicDiscoveryError("Atomic Insight 批次大小必须大于 0。")
    return [
        list(reviews[start : start + batch_size])
        for start in range(0, len(reviews), batch_size)
    ]


def validate_insight_batch(
    result: InsightExtractionBatch, batch_review_ids: set[str]
) -> None:
    """确保单个批次的每条评论恰好进入 Insight 或 OTHER。"""
    insight_review_ids = {insight.review_id for insight in result.insights}
    other_review_ids = set(result.other_review_ids)
    invalid_insight_reviews = sorted(insight_review_ids - batch_review_ids)
    invalid_other_reviews = sorted(other_review_ids - batch_review_ids)
    overlap = sorted(insight_review_ids & other_review_ids)
    unaccounted = sorted(batch_review_ids - insight_review_ids - other_review_ids)
    errors: list[str] = []
    if invalid_insight_reviews:
        errors.append(
            "Insight 引用了不属于本批次的评论："
            + ", ".join(invalid_insight_reviews)
        )
    if invalid_other_reviews:
        errors.append(
            "OTHER 引用了不属于本批次的评论：" + ", ".join(invalid_other_reviews)
        )
    if overlap:
        errors.append("评论同时产生 Insight 并进入 OTHER：" + ", ".join(overlap))
    if unaccounted:
        errors.append("本批评论未被处理：" + ", ".join(unaccounted))
    if errors:
        if (
            unaccounted
            and not invalid_insight_reviews
            and not invalid_other_reviews
            and not overlap
        ):
            raise IncompleteInsightBatchError(unaccounted)
        raise TopicDiscoveryError("；".join(errors))


def merge_insight_batch_repair(
    original: InsightExtractionBatch,
    repair: InsightExtractionBatch,
    batch_review_ids: set[str],
    missing_review_ids: set[str],
) -> InsightExtractionBatch:
    """合并一次遗漏评论补提取，并重新执行完整批次质量门。"""
    validate_insight_batch(repair, missing_review_ids)
    merged = InsightExtractionBatch(
        insights=[*original.insights, *repair.insights],
        other_review_ids=[
            *original.other_review_ids,
            *repair.other_review_ids,
        ],
        limitations=[
            *original.limitations,
            f"有限补提取处理了 {len(missing_review_ids)} 条首轮遗漏评论。",
            *repair.limitations,
        ],
    )
    validate_insight_batch(merged, batch_review_ids)
    return merged


def materialize_insights(
    batch_results: Sequence[InsightExtractionBatch],
) -> list[AtomicInsight]:
    """按批次和模型输出顺序，由 Python 分配全局唯一 Insight ID。"""
    return [
        AtomicInsight(
            insight_id=f"INSIGHT-{index:04d}",
            review_id=candidate.review_id,
            statement=candidate.statement,
            sentiment=candidate.sentiment,
        )
        for index, candidate in enumerate(
            (
                candidate
                for batch_result in batch_results
                for candidate in batch_result.insights
            ),
            start=1,
        )
    ]


def _derive_representative_review_ids(
    insight_ids: Sequence[str],
    insight_by_id: dict[str, AtomicInsight],
    review_order: dict[str, int],
) -> list[str]:
    """优先选择该 Topic 内 Insight 数最多、输入顺序更早的去重评论。"""
    counts = Counter(insight_by_id[insight_id].review_id for insight_id in insight_ids)
    ranked = sorted(
        counts,
        key=lambda review_id: (-counts[review_id], review_order[review_id]),
    )
    return ranked[:MAX_REPRESENTATIVE_REVIEWS]


def _aggregation_assignment_issues(
    draft: TopicAggregationDraft,
    insights: Sequence[AtomicInsight],
) -> tuple[list[str], list[str], list[str]]:
    """返回非法、重复和遗漏 Insight ID，供质量门与有限修复共用。"""
    valid_insight_ids = {insight.insight_id for insight in insights}
    assigned_ids = [
        insight_id for topic in draft.topics for insight_id in topic.insight_ids
    ]
    invalid_ids = sorted(set(assigned_ids) - valid_insight_ids)
    duplicated_ids = sorted(
        insight_id
        for insight_id, count in Counter(assigned_ids).items()
        if count > 1
    )
    unassigned_ids = sorted(valid_insight_ids - set(assigned_ids))
    return invalid_ids, duplicated_ids, unassigned_ids


def apply_topic_repair(
    draft: TopicAggregationDraft,
    repair: TopicAggregationRepairDraft,
    insights: Sequence[AtomicInsight],
) -> TopicAggregationDraft:
    """只合并遗漏 Insight 的一次修复，拒绝改写或复制现有分组。"""
    invalid_ids, duplicated_ids, missing_ids = _aggregation_assignment_issues(
        draft, insights
    )
    if invalid_ids or duplicated_ids or not missing_ids:
        raise TopicDiscoveryError(
            "只有纯遗漏 Insight 的聚合结果可以进入有限修复。"
        )

    existing_candidate_ids = {topic.candidate_id for topic in draft.topics}
    assignment_by_candidate = {
        assignment.candidate_id: assignment.insight_ids
        for assignment in repair.existing_topic_assignments
    }
    repair_insight_ids = [
        insight_id
        for assignment in repair.existing_topic_assignments
        for insight_id in assignment.insight_ids
    ] + [
        insight_id
        for topic in repair.new_topics
        for insight_id in topic.insight_ids
    ]
    errors: list[str] = []
    unknown_candidates = sorted(
        set(assignment_by_candidate) - existing_candidate_ids
    )
    conflicting_new_candidates = sorted(
        {topic.candidate_id for topic in repair.new_topics}
        & existing_candidate_ids
    )
    invalid_repair_insights = sorted(set(repair_insight_ids) - set(missing_ids))
    still_missing = sorted(set(missing_ids) - set(repair_insight_ids))
    if unknown_candidates:
        errors.append(
            "修复引用了不存在的 Topic Candidate："
            + ", ".join(unknown_candidates)
        )
    if conflicting_new_candidates:
        errors.append(
            "新 Topic Candidate ID 与现有 Topic 重复："
            + ", ".join(conflicting_new_candidates)
        )
    if invalid_repair_insights:
        errors.append(
            "修复引用了非遗漏 Insight：" + ", ".join(invalid_repair_insights)
        )
    if still_missing:
        errors.append("修复后仍有遗漏 Insight：" + ", ".join(still_missing))
    if errors:
        raise TopicDiscoveryError("；".join(errors))

    repaired_topics = [
        topic.model_copy(
            update={
                "insight_ids": [
                    *topic.insight_ids,
                    *assignment_by_candidate.get(topic.candidate_id, []),
                ]
            }
        )
        for topic in draft.topics
    ]
    repaired_topics.extend(repair.new_topics)
    return TopicAggregationDraft(
        topics=repaired_topics,
        limitations=[
            *draft.limitations,
            f"Topic 聚合有限修复补充了 {len(missing_ids)} 条遗漏 Insight。",
            *repair.limitations,
        ],
    )


def apply_topic_aggregation(
    draft: TopicAggregationDraft,
    insights: Sequence[AtomicInsight],
    reviews: Sequence[Review],
    other_review_ids: Sequence[str],
    limitations: Sequence[str],
    extraction_batch_count: int,
) -> TopicDiscoveryResult:
    """校验全量分组，并由 Python 生成 Topic ID 与代表评论。"""
    insight_by_id = {insight.insight_id: insight for insight in insights}
    valid_review_ids = {review.review_id for review in reviews}
    invalid_ids, duplicated_ids, unassigned_ids = _aggregation_assignment_issues(
        draft, insights
    )
    errors: list[str] = []
    invalid_insight_reviews = sorted(
        {
            insight.review_id
            for insight in insights
            if insight.review_id not in valid_review_ids
        }
    )
    invalid_other_reviews = sorted(set(other_review_ids) - valid_review_ids)
    if invalid_insight_reviews:
        errors.append(
            "Insight 引用了不存在的 Review：" + ", ".join(invalid_insight_reviews)
        )
    if invalid_other_reviews:
        errors.append(
            "OTHER 引用了不存在的 Review：" + ", ".join(invalid_other_reviews)
        )
    if invalid_ids:
        errors.append("Topic 引用了不存在的 Insight：" + ", ".join(invalid_ids))
    if duplicated_ids:
        errors.append("Insight 被分入多个 Topic：" + ", ".join(duplicated_ids))
    if unassigned_ids:
        errors.append("Insight 没有归入 Topic：" + ", ".join(unassigned_ids))
    if errors:
        if (
            unassigned_ids
            and not invalid_insight_reviews
            and not invalid_other_reviews
            and not invalid_ids
            and not duplicated_ids
        ):
            raise IncompleteTopicAggregationError(unassigned_ids)
        raise TopicDiscoveryError("；".join(errors))

    review_order = {review.review_id: index for index, review in enumerate(reviews)}
    topics = [
        Topic(
            topic_id=f"TOPIC-{index:03d}",
            name=candidate.name,
            description=candidate.description,
            insight_ids=candidate.insight_ids,
            representative_review_ids=_derive_representative_review_ids(
                candidate.insight_ids, insight_by_id, review_order
            ),
        )
        for index, candidate in enumerate(draft.topics, start=1)
    ]
    result = TopicDiscoveryResult(
        insights=list(insights),
        topics=topics,
        other_review_ids=list(other_review_ids),
        limitations=[*limitations, *draft.limitations],
        extraction_batch_count=extraction_batch_count,
    )
    validate_topic_references(result, set(review_order))
    return result


def validate_topic_references(
    result: TopicDiscoveryResult, valid_review_ids: set[str]
) -> None:
    """校验最终结果的 Review/Insight/Topic 引用和完整覆盖。"""
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
    """分批提取 Insight，再统一聚合 Topic 的结构化模型服务。"""

    def __init__(
        self,
        config: ModelConfig | None = None,
        batch_size: int = DEFAULT_INSIGHT_BATCH_SIZE,
    ) -> None:
        self.config = config or ModelConfig.from_env()
        if batch_size < 1:
            raise TopicDiscoveryError("Atomic Insight 批次大小必须大于 0。")
        self.batch_size = batch_size

    def discover(
        self, reviews: Sequence[Review], analysis_goal: str
    ) -> TopicDiscoveryResult:
        if not reviews:
            raise TopicDiscoveryError("没有可用于主题发现的有效评论。")

        current_stage = "初始化模型客户端"
        try:
            import instructor
            from openai import OpenAI

            client = instructor.from_openai(
                OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url,
                )
            )
            batches = batch_reviews(reviews, self.batch_size)
            batch_results: list[InsightExtractionBatch] = []
            extraction_limitations: list[str] = []
            for batch_index, batch in enumerate(batches, start=1):
                current_stage = f"Atomic Insight 批次 {batch_index}/{len(batches)}"
                batch_result = client.chat.completions.create(
                    model=self.config.model,
                    response_model=InsightExtractionBatch,
                    messages=build_insight_extraction_messages(
                        batch, analysis_goal, batch_index, len(batches)
                    ),
                    max_retries=1,
                    **build_model_request_options(self.config),
                )
                batch_review_ids = {review.review_id for review in batch}
                try:
                    validate_insight_batch(batch_result, batch_review_ids)
                except IncompleteInsightBatchError as incomplete_error:
                    missing_review_ids = set(incomplete_error.missing_review_ids)
                    missing_reviews = [
                        review
                        for review in batch
                        if review.review_id in missing_review_ids
                    ]
                    current_stage = (
                        f"Atomic Insight 批次 {batch_index}/{len(batches)} "
                        "遗漏评论有限补提取"
                    )
                    repair_result = client.chat.completions.create(
                        model=self.config.model,
                        response_model=InsightExtractionBatch,
                        messages=build_insight_repair_messages(
                            missing_reviews,
                            analysis_goal,
                            batch_index,
                            len(batches),
                        ),
                        max_retries=1,
                        **build_model_request_options(self.config),
                    )
                    batch_result = merge_insight_batch_repair(
                        batch_result,
                        repair_result,
                        batch_review_ids,
                        missing_review_ids,
                    )
                batch_results.append(batch_result)
                extraction_limitations.extend(
                    f"批次 {batch_index}：{limitation}"
                    for limitation in batch_result.limitations
                )

            insights = materialize_insights(batch_results)
            other_review_ids = [
                review_id
                for batch_result in batch_results
                for review_id in batch_result.other_review_ids
            ]
            if not insights:
                result = TopicDiscoveryResult(
                    insights=[],
                    topics=[],
                    other_review_ids=other_review_ids,
                    limitations=extraction_limitations,
                    extraction_batch_count=len(batches),
                )
                validate_topic_references(
                    result, {review.review_id for review in reviews}
                )
                return result

            current_stage = "全量 Atomic Insight 统一聚合 Topic"
            aggregation = client.chat.completions.create(
                model=self.config.model,
                response_model=TopicAggregationDraft,
                messages=build_topic_aggregation_messages(insights, analysis_goal),
                max_retries=1,
                **build_model_request_options(self.config),
            )
            try:
                return apply_topic_aggregation(
                    aggregation,
                    insights,
                    reviews,
                    other_review_ids,
                    extraction_limitations,
                    len(batches),
                )
            except IncompleteTopicAggregationError as incomplete_error:
                missing_ids = incomplete_error.missing_insight_ids
                current_stage = "遗漏 Atomic Insight 有限聚合修复"
                insight_by_id = {
                    insight.insight_id: insight for insight in insights
                }
                repair = client.chat.completions.create(
                    model=self.config.model,
                    response_model=TopicAggregationRepairDraft,
                    messages=build_topic_repair_messages(
                        aggregation,
                        [insight_by_id[insight_id] for insight_id in missing_ids],
                        analysis_goal,
                    ),
                    max_retries=1,
                    **build_model_request_options(self.config),
                )
                repaired_aggregation = apply_topic_repair(
                    aggregation, repair, insights
                )
                return apply_topic_aggregation(
                    repaired_aggregation,
                    insights,
                    reviews,
                    other_review_ids,
                    extraction_limitations,
                    len(batches),
                )
        except TopicDiscoveryError:
            raise
        except Exception as error:
            raise TopicDiscoveryError(
                f"{current_stage} 的模型调用或结构化输出失败，本阶段已停止。"
                "请检查模型配置、网络和模型兼容性。"
                f"服务商返回：{safe_provider_error(error, self.config.api_key)}"
            ) from error
