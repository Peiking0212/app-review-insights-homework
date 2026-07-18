"""Evidence Finding 的模型草拟、确定性校验和置信度计算。"""

from __future__ import annotations

from collections.abc import Sequence

from src.config import ModelConfig
from src.finding_prompts import build_finding_messages
from src.schemas import (
    AtomicInsight,
    DiscoveryItem,
    Finding,
    FindingDraft,
    FindingGenerationResult,
    Review,
    TopicDiscoveryResult,
)
from src.topic_discovery import (
    TopicDiscoveryError,
    build_model_request_options,
    safe_provider_error,
    validate_topic_references,
)


MIN_FINDING_SUPPORT = 2


class FindingGenerationError(RuntimeError):
    """Finding 无法在证据约束下安全生成。"""


def calculate_confidence(
    support_count: int, conflict_count: int, topic_review_count: int
) -> str:
    """由去重评论数确定置信度，不接受模型自行估算。"""
    if topic_review_count <= 0 or support_count <= 0:
        return "low"
    support_share = support_count / topic_review_count
    if (
        support_count >= 5
        and support_share >= 0.5
        and conflict_count * 4 <= support_count
    ):
        return "high"
    if support_count >= 2 and conflict_count < support_count:
        return "medium"
    return "low"


def _evidence_relationships(
    topic_result: TopicDiscoveryResult,
) -> tuple[dict[str, AtomicInsight], dict[str, str], dict[str, set[str]]]:
    insight_by_id = {
        insight.insight_id: insight for insight in topic_result.insights
    }
    topic_by_insight: dict[str, str] = {}
    all_reviews: dict[str, set[str]] = {}
    for topic in topic_result.topics:
        for insight_id in topic.insight_ids:
            topic_by_insight[insight_id] = topic.topic_id
        topic_insights = [
            insight_by_id[insight_id]
            for insight_id in topic.insight_ids
            if insight_id in insight_by_id
        ]
        all_reviews[topic.topic_id] = {
            insight.review_id for insight in topic_insights
        }
    return insight_by_id, topic_by_insight, all_reviews


def apply_finding_quality_gate(
    draft: FindingDraft,
    topic_result: TopicDiscoveryResult,
    valid_review_ids: set[str],
) -> FindingGenerationResult:
    """拒绝非法证据，并把样本不足候选降级为 Discovery。"""
    valid_topic_ids = {topic.topic_id for topic in topic_result.topics}
    insight_by_id, topic_by_insight, all_reviews = _evidence_relationships(
        topic_result
    )
    valid_insight_ids = set(insight_by_id)
    errors: list[str] = []
    covered_topic_ids: set[str] = set()

    for candidate in draft.candidates:
        cited_insight_ids = set(candidate.supporting_insight_ids) | set(
            candidate.conflicting_insight_ids
        )
        invalid_insights = sorted(cited_insight_ids - valid_insight_ids)
        if invalid_insights:
            errors.append(
                f"{candidate.candidate_id} 引用了不存在的 Insight："
                + ", ".join(invalid_insights)
            )
            continue
        covered_topic_ids.update(
            topic_by_insight[insight_id] for insight_id in cited_insight_ids
        )
        invalid_support = sorted(
            insight_id
            for insight_id in candidate.supporting_insight_ids
            if insight_by_id[insight_id].sentiment not in {"negative", "mixed"}
        )
        invalid_conflicts = sorted(
            insight_id
            for insight_id in candidate.conflicting_insight_ids
            if insight_by_id[insight_id].sentiment not in {"positive", "mixed"}
        )
        support_review_ids = {
            insight_by_id[insight_id].review_id
            for insight_id in candidate.supporting_insight_ids
        }
        conflict_review_ids = {
            insight_by_id[insight_id].review_id
            for insight_id in candidate.conflicting_insight_ids
        }
        invalid_reviews = sorted(
            (support_review_ids | conflict_review_ids) - valid_review_ids
        )
        overlapping_reviews = sorted(support_review_ids & conflict_review_ids)
        if invalid_support:
            errors.append(
                f"{candidate.candidate_id} 的支持 Insight 不是 negative 或 mixed："
                + ", ".join(invalid_support)
            )
        if invalid_conflicts:
            errors.append(
                f"{candidate.candidate_id} 的冲突 Insight 不是 positive 或 mixed："
                + ", ".join(invalid_conflicts)
            )
        if invalid_reviews:
            errors.append(
                f"{candidate.candidate_id} 推导出不存在的 Review："
                + ", ".join(invalid_reviews)
            )
        if overlapping_reviews:
            errors.append(
                f"{candidate.candidate_id} 的同一 Review 同时支持和冲突："
                + ", ".join(overlapping_reviews)
            )

    for discovery in draft.discovery_candidates:
        invalid_insights = sorted(set(discovery.insight_ids) - valid_insight_ids)
        if invalid_insights:
            errors.append(
                "Discovery 引用了不存在的 Insight："
                + ", ".join(invalid_insights)
            )
            continue
        covered_topic_ids.update(
            topic_by_insight[insight_id] for insight_id in discovery.insight_ids
        )
        discovery_review_ids = {
            insight_by_id[insight_id].review_id
            for insight_id in discovery.insight_ids
        }
        invalid_reviews = sorted(discovery_review_ids - valid_review_ids)
        if invalid_reviews:
            errors.append(
                "Discovery 推导出不存在的 Review："
                + ", ".join(invalid_reviews)
            )

    uncovered_topics = sorted(valid_topic_ids - covered_topic_ids)
    if uncovered_topics:
        errors.append("以下 Topic 未被分析：" + ", ".join(uncovered_topics))
    if errors:
        raise FindingGenerationError("；".join(errors))

    findings: list[Finding] = []
    discovery_items: list[DiscoveryItem] = []
    for candidate in draft.candidates:
        supporting_review_ids = list(
            dict.fromkeys(
                insight_by_id[insight_id].review_id
                for insight_id in candidate.supporting_insight_ids
            )
        )
        conflicting_review_ids = list(
            dict.fromkeys(
                insight_by_id[insight_id].review_id
                for insight_id in candidate.conflicting_insight_ids
            )
        )
        source_topic_ids = list(
            dict.fromkeys(
                topic_by_insight[insight_id]
                for insight_id in [
                    *candidate.supporting_insight_ids,
                    *candidate.conflicting_insight_ids,
                ]
            )
        )
        support_count = len(supporting_review_ids)
        source_topic_reviews = set().union(
            *(all_reviews[topic_id] for topic_id in source_topic_ids)
        )
        if support_count < MIN_FINDING_SUPPORT:
            discovery_items.append(
                DiscoveryItem(
                    discovery_id=f"DISC-{len(discovery_items) + 1:03d}",
                    title=candidate.title,
                    reason=(
                        f"当前只有 {support_count} 条去重支持评论，"
                        f"低于进入 Finding 的最小证据门槛 {MIN_FINDING_SUPPORT}。"
                    ),
                    source_topic_ids=source_topic_ids,
                    review_ids=supporting_review_ids,
                )
            )
            continue
        findings.append(
            Finding(
                finding_id=f"FIND-{len(findings) + 1:03d}",
                title=candidate.title,
                description=candidate.description,
                source_topic_ids=source_topic_ids,
                supporting_review_ids=supporting_review_ids,
                conflicting_review_ids=conflicting_review_ids,
                severity=candidate.severity,
                confidence=calculate_confidence(
                    support_count,
                    len(conflicting_review_ids),
                    len(source_topic_reviews),
                ),
                limitations=candidate.limitations,
            )
        )

    for discovery in draft.discovery_candidates:
        source_topic_ids = list(
            dict.fromkeys(
                topic_by_insight[insight_id] for insight_id in discovery.insight_ids
            )
        )
        review_ids = list(
            dict.fromkeys(
                insight_by_id[insight_id].review_id
                for insight_id in discovery.insight_ids
            )
        )
        discovery_items.append(
            DiscoveryItem(
                discovery_id=f"DISC-{len(discovery_items) + 1:03d}",
                title=discovery.title,
                reason=discovery.reason,
                source_topic_ids=source_topic_ids,
                review_ids=review_ids,
            )
        )

    return FindingGenerationResult(
        findings=findings,
        discovery_items=discovery_items,
        limitations=[*topic_result.limitations, *draft.limitations],
    )


class FindingAnalysisService:
    """通过模型草拟 Finding，再由 Python 质量门生成最终结果。"""

    def __init__(self, config: ModelConfig | None = None) -> None:
        self.config = config or ModelConfig.from_env()

    def generate(
        self,
        reviews: Sequence[Review],
        topic_result: TopicDiscoveryResult,
        analysis_goal: str,
    ) -> FindingGenerationResult:
        if not topic_result.topics:
            raise FindingGenerationError("没有可用于 Finding 的已验证 Topic。")
        valid_review_ids = {review.review_id for review in reviews}
        try:
            validate_topic_references(topic_result, valid_review_ids)
            import instructor
            from openai import OpenAI

            client = instructor.from_openai(
                OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url,
                )
            )
            draft = client.chat.completions.create(
                model=self.config.model,
                response_model=FindingDraft,
                messages=build_finding_messages(
                    reviews, topic_result, analysis_goal
                ),
                max_retries=1,
                **build_model_request_options(self.config),
            )
        except FindingGenerationError:
            raise
        except TopicDiscoveryError as error:
            raise FindingGenerationError(
                f"上游 Topic 校验失败，本阶段已停止：{error}"
            ) from error
        except Exception as error:
            raise FindingGenerationError(
                "模型调用或 Finding 结构化输出失败，本阶段已停止。"
                f"服务商返回：{safe_provider_error(error, self.config.api_key)}"
            ) from error
        return apply_finding_quality_gate(
            draft, topic_result, valid_review_ids
        )
