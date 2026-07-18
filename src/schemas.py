"""ReviewScope AI 全流程使用的可追溯数据模型。"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """拒绝未声明字段并自动清理字符串两侧空白。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _validate_id_list(values: list[str], prefix: str) -> list[str]:
    """验证引用 ID 的前缀、非空和唯一性。"""
    cleaned: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized.startswith(prefix) or len(normalized) == len(prefix):
            raise ValueError(f"引用 ID 必须以 {prefix} 开头")
        if normalized in cleaned:
            raise ValueError(f"引用 ID 不得重复：{normalized}")
        cleaned.append(normalized)
    return cleaned


class Review(StrictModel):
    """清洗后、可以参与分析的一条真实或明确标记的示例评论。"""

    review_id: str = Field(pattern=r"^REV-[A-Za-z0-9_-]+$")
    source_id: str = Field(min_length=1)
    title: str = ""
    content: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    version: Optional[str] = None
    published_at: Optional[date] = None
    storefront: str = Field(default="us", pattern=r"^us$")
    source: str = Field(min_length=1)


class Topic(StrictModel):
    """根据当前评论动态发现的主题，而不是预设行业分类。"""

    topic_id: str = Field(pattern=r"^TOPIC-[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    insight_ids: list[str] = Field(min_length=1)
    representative_review_ids: list[str] = Field(min_length=1)

    @field_validator("insight_ids")
    @classmethod
    def validate_insight_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "INSIGHT-")

    @field_validator("representative_review_ids")
    @classmethod
    def validate_review_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "REV-")


class AtomicInsight(StrictModel):
    """从一条评论中提取的单一方面、单一情绪的原子观点。"""

    insight_id: str = Field(pattern=r"^INSIGHT-[A-Za-z0-9_-]+$")
    review_id: str = Field(pattern=r"^REV-[A-Za-z0-9_-]+$")
    statement: str = Field(min_length=1)
    sentiment: Literal["positive", "negative", "neutral", "mixed"]


class TopicDiscoveryResult(StrictModel):
    """动态主题阶段的完整结构化输出。"""

    insights: list[AtomicInsight] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    other_review_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("other_review_ids")
    @classmethod
    def validate_other_review_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "REV-")

    @model_validator(mode="after")
    def ids_must_be_unique(self) -> "TopicDiscoveryResult":
        insight_ids = [insight.insight_id for insight in self.insights]
        topic_ids = [topic.topic_id for topic in self.topics]
        if len(insight_ids) != len(set(insight_ids)):
            raise ValueError("Atomic Insight ID 不得重复")
        if len(topic_ids) != len(set(topic_ids)):
            raise ValueError("Topic ID 不得重复")
        assigned_insight_ids = [
            insight_id for topic in self.topics for insight_id in topic.insight_ids
        ]
        assignment_counts = Counter(assigned_insight_ids)
        multiply_assigned = sorted(
            insight_id
            for insight_id, count in assignment_counts.items()
            if count > 1
        )
        if multiply_assigned:
            raise ValueError(
                "Atomic Insight 只能属于一个 Topic："
                + ", ".join(multiply_assigned)
            )
        return self


class Finding(StrictModel):
    """由评论证据支持的具体用户问题。"""

    finding_id: str = Field(pattern=r"^FIND-[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_topic_ids: list[str] = Field(min_length=1)
    supporting_review_ids: list[str] = Field(min_length=1)
    conflicting_review_ids: list[str] = Field(default_factory=list)
    severity: str = Field(pattern=r"^(low|medium|high|critical)$")
    confidence: str = Field(pattern=r"^(low|medium|high)$")
    limitations: list[str] = Field(default_factory=list)

    @field_validator("source_topic_ids")
    @classmethod
    def validate_topic_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "TOPIC-")

    @field_validator("supporting_review_ids", "conflicting_review_ids")
    @classmethod
    def validate_review_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "REV-")

    @model_validator(mode="after")
    def evidence_must_not_conflict(self) -> "Finding":
        overlap = set(self.supporting_review_ids) & set(self.conflicting_review_ids)
        if overlap:
            raise ValueError(
                "同一评论不能同时作为支持和冲突证据："
                + ", ".join(sorted(overlap))
            )
        return self


class FindingCandidate(StrictModel):
    """模型草拟的问题候选；统计数量和置信度不由模型填写。"""

    candidate_id: str = Field(pattern=r"^CAND-[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    supporting_insight_ids: list[str] = Field(min_length=1)
    conflicting_insight_ids: list[str] = Field(default_factory=list)
    severity: Literal["low", "medium", "high", "critical"]
    limitations: list[str] = Field(default_factory=list)

    @field_validator("supporting_insight_ids", "conflicting_insight_ids")
    @classmethod
    def validate_insight_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "INSIGHT-")

    @model_validator(mode="after")
    def evidence_must_not_overlap(self) -> "FindingCandidate":
        overlap = set(self.supporting_insight_ids) & set(
            self.conflicting_insight_ids
        )
        if overlap:
            raise ValueError(
                "同一 Insight 不能同时作为支持和冲突证据："
                + ", ".join(sorted(overlap))
            )
        return self


class DiscoveryCandidate(StrictModel):
    """模型认为暂时证据不足、不应升级为 Finding 的线索。"""

    title: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    insight_ids: list[str] = Field(min_length=1)

    @field_validator("insight_ids")
    @classmethod
    def validate_insight_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "INSIGHT-")


class FindingDraft(StrictModel):
    """模型输出的候选结果，进入下游前必须通过 Python 质量门。"""

    candidates: list[FindingCandidate] = Field(default_factory=list)
    discovery_candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def candidate_ids_must_be_unique(self) -> "FindingDraft":
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Finding Candidate ID 不得重复")
        cited_insight_ids = [
            insight_id
            for candidate in self.candidates
            for insight_id in [
                *candidate.supporting_insight_ids,
                *candidate.conflicting_insight_ids,
            ]
        ] + [
            insight_id
            for discovery in self.discovery_candidates
            for insight_id in discovery.insight_ids
        ]
        duplicated = sorted(
            insight_id
            for insight_id, count in Counter(cited_insight_ids).items()
            if count > 1
        )
        if duplicated:
            raise ValueError(
                "同一 Insight 不能被多个 Finding/Discovery 重复使用："
                + ", ".join(duplicated)
            )
        return self


class DiscoveryItem(StrictModel):
    """经过质量门确认的证据不足线索。"""

    discovery_id: str = Field(pattern=r"^DISC-[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    source_topic_ids: list[str] = Field(min_length=1)
    review_ids: list[str] = Field(min_length=1)

    @field_validator("source_topic_ids")
    @classmethod
    def validate_topic_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "TOPIC-")

    @field_validator("review_ids")
    @classmethod
    def validate_review_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "REV-")


class FindingGenerationResult(StrictModel):
    """可以进入 UI 和后续阶段的 Evidence Finding 结果。"""

    findings: list[Finding] = Field(default_factory=list)
    discovery_items: list[DiscoveryItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Requirement(StrictModel):
    """能够追溯到 Finding 和原始评论的产品需求。"""

    requirement_id: str = Field(pattern=r"^REQ-[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1)
    release: str = Field(min_length=1)
    priority: str = Field(pattern=r"^P[0-3]$")
    description: str = Field(min_length=1)
    source_finding_ids: list[str] = Field(min_length=1)
    source_review_ids: list[str] = Field(min_length=1)
    in_scope: list[str] = Field(min_length=1)
    out_of_scope: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(min_length=1)

    @field_validator("source_finding_ids")
    @classmethod
    def validate_finding_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "FIND-")

    @field_validator("source_review_ids")
    @classmethod
    def validate_review_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "REV-")


class RequirementCandidate(StrictModel):
    """模型草拟的需求；证据评论、版本和优先级由 Python 补全。"""

    candidate_id: str = Field(pattern=r"^REQC-[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_finding_ids: list[str] = Field(min_length=1)
    in_scope: list[str] = Field(min_length=1)
    out_of_scope: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(min_length=1)

    @field_validator("source_finding_ids")
    @classmethod
    def validate_finding_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "FIND-")


class ReleaseCandidate(StrictModel):
    """模型草拟的版本目标以及候选需求分组。"""

    release: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    requirement_candidate_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)

    @field_validator("requirement_candidate_ids")
    @classmethod
    def validate_candidate_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "REQC-")


class DeferredFinding(StrictModel):
    """本轮不进入版本规划、但给出明确验证动作的 Finding。"""

    finding_id: str = Field(pattern=r"^FIND-[A-Za-z0-9_-]+$")
    reason: str = Field(min_length=1)
    next_validation: str = Field(min_length=1)


class ProductHypothesis(StrictModel):
    """没有评论证据支持的产品假设，不得伪装成正式需求。"""

    hypothesis_id: str = Field(pattern=r"^HYP-[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    validation_plan: str = Field(min_length=1)


class ProductPlanningDraft(StrictModel):
    """模型输出的版本规划与 PRD 草稿，必须再经过 Python 质量门。"""

    prd_title: str = Field(min_length=1)
    executive_summary: str = Field(min_length=1)
    requirements: list[RequirementCandidate] = Field(min_length=1, max_length=6)
    releases: list[ReleaseCandidate] = Field(min_length=1, max_length=3)
    deferred_findings: list[DeferredFinding] = Field(default_factory=list)
    product_hypotheses: list[ProductHypothesis] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def draft_ids_must_be_unique(self) -> "ProductPlanningDraft":
        groups = {
            "Requirement Candidate": [item.candidate_id for item in self.requirements],
            "Release": [item.release for item in self.releases],
            "Deferred Finding": [item.finding_id for item in self.deferred_findings],
            "Product Hypothesis": [item.hypothesis_id for item in self.product_hypotheses],
        }
        for label, values in groups.items():
            if len(values) != len(set(values)):
                raise ValueError(f"{label} ID/名称不得重复")
        return self


class ReleasePlanItem(StrictModel):
    """通过质量门后的版本计划。"""

    release: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    requirement_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)

    @field_validator("requirement_ids")
    @classmethod
    def validate_requirement_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "REQ-")


class ProductPlanResult(StrictModel):
    """可展示、可追溯，并能进入测试用例阶段的最终规划结果。"""

    prd_title: str = Field(min_length=1)
    executive_summary: str = Field(min_length=1)
    releases: list[ReleasePlanItem] = Field(min_length=1)
    requirements: list[Requirement] = Field(min_length=1)
    deferred_findings: list[DeferredFinding] = Field(default_factory=list)
    product_hypotheses: list[ProductHypothesis] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TestCase(StrictModel):
    """验证需求是否解决来源评论问题的测试用例。"""

    test_case_id: str = Field(pattern=r"^TC-[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1)
    requirement_id: str = Field(pattern=r"^REQ-[A-Za-z0-9_-]+$")
    source_review_ids: list[str] = Field(min_length=1)
    priority: str = Field(pattern=r"^P[0-3]$")
    test_type: str = Field(min_length=1)
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(min_length=1)
    expected_results: list[str] = Field(min_length=1)

    @field_validator("source_review_ids")
    @classmethod
    def validate_review_ids(cls, values: list[str]) -> list[str]:
        return _validate_id_list(values, "REV-")


class TestCaseCandidate(StrictModel):
    """模型草拟的测试场景；证据、优先级和最终 ID 由 Python 补全。"""

    candidate_id: str = Field(pattern=r"^TCC-[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1)
    requirement_id: str = Field(pattern=r"^REQ-[A-Za-z0-9_-]+$")
    scenario_type: Literal["normal", "negative", "boundary"]
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(min_length=1)
    expected_results: list[str] = Field(min_length=1)


class TestGenerationDraft(StrictModel):
    """模型生成的测试草稿，进入 UI 前必须通过确定性追溯质量门。"""

    test_cases: list[TestCaseCandidate] = Field(min_length=1, max_length=30)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def candidate_ids_must_be_unique(self) -> "TestGenerationDraft":
        candidate_ids = [item.candidate_id for item in self.test_cases]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Test Case Candidate ID 不得重复")
        return self


class TestGenerationResult(StrictModel):
    """可以展示并参与端到端追溯检查的最终测试结果。"""

    test_cases: list[TestCase] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
