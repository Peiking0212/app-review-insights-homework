"""版本规划与 PRD 的模型草拟、确定性证据派生和质量门。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from src.config import ModelConfig
from src.finding_analysis import calculate_finding_quality
from src.planning_prompts import build_planning_messages
from src.schemas import (
    Finding,
    FindingGenerationResult,
    ProductPlanResult,
    ProductPlanningDraft,
    ReleasePlanItem,
    Requirement,
    Review,
    TopicDiscoveryResult,
)
from src.topic_discovery import build_model_request_options, safe_provider_error


class ProductPlanningError(RuntimeError):
    """版本规划无法在证据约束下安全生成。"""


_PRIORITY_BY_SEVERITY = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
}
_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def calculate_requirement_priority(findings: Sequence[Finding]) -> str:
    """按最严重 Finding 计算优先级；全为低置信度时保守降一级。"""
    if not findings:
        raise ProductPlanningError("需求没有可用于计算优先级的 Finding。")
    priority = min(
        (_PRIORITY_BY_SEVERITY[finding.severity] for finding in findings),
        key=_PRIORITY_ORDER.__getitem__,
    )
    if all(finding.confidence == "low" for finding in findings):
        priority = {"P0": "P1", "P1": "P2", "P2": "P3", "P3": "P3"}[
            priority
        ]
    return priority


def validate_planning_input(
    reviews: Sequence[Review],
    topic_result: TopicDiscoveryResult,
    finding_result: FindingGenerationResult,
) -> None:
    """在调用模型前验证上游质量，失败时立即停止下游生成。"""
    if not finding_result.findings:
        raise ProductPlanningError(
            "没有达到证据门槛的 Evidence Finding，不能生成正式 PRD。"
        )
    quality = calculate_finding_quality(
        finding_result,
        topic_result,
        {review.review_id for review in reviews},
    )
    if not quality.quality_gate_passed:
        raise ProductPlanningError(
            "Finding Quality Gate 未通过，版本规划与 PRD 已停止。"
        )


def apply_planning_quality_gate(
    draft: ProductPlanningDraft,
    finding_result: FindingGenerationResult,
    valid_review_ids: set[str],
) -> ProductPlanResult:
    """校验覆盖关系，并从 Finding 确定性派生 Review、优先级与最终 ID。"""
    finding_by_id = {
        finding.finding_id: finding for finding in finding_result.findings
    }
    candidate_by_id = {
        candidate.candidate_id: candidate for candidate in draft.requirements
    }
    errors: list[str] = []

    referenced_finding_ids = {
        finding_id
        for candidate in draft.requirements
        for finding_id in candidate.source_finding_ids
    }
    invalid_finding_ids = sorted(referenced_finding_ids - set(finding_by_id))
    if invalid_finding_ids:
        errors.append("需求引用了不存在的 Finding：" + ", ".join(invalid_finding_ids))

    deferred_ids = {item.finding_id for item in draft.deferred_findings}
    invalid_deferred_ids = sorted(deferred_ids - set(finding_by_id))
    if invalid_deferred_ids:
        errors.append("延期项引用了不存在的 Finding：" + ", ".join(invalid_deferred_ids))
    overlap = sorted(referenced_finding_ids & deferred_ids)
    if overlap:
        errors.append("Finding 不能同时进入需求和延期项：" + ", ".join(overlap))
    omitted = sorted(set(finding_by_id) - referenced_finding_ids - deferred_ids)
    if omitted:
        errors.append("以下 Finding 未被处理：" + ", ".join(omitted))

    assigned_candidate_ids = [
        candidate_id
        for release in draft.releases
        for candidate_id in release.requirement_candidate_ids
    ]
    invalid_candidate_ids = sorted(set(assigned_candidate_ids) - set(candidate_by_id))
    if invalid_candidate_ids:
        errors.append(
            "版本引用了不存在的候选需求：" + ", ".join(invalid_candidate_ids)
        )
    assignment_counts = Counter(assigned_candidate_ids)
    duplicated_assignments = sorted(
        candidate_id
        for candidate_id, count in assignment_counts.items()
        if count > 1
    )
    if duplicated_assignments:
        errors.append(
            "候选需求只能进入一个版本：" + ", ".join(duplicated_assignments)
        )
    unassigned = sorted(set(candidate_by_id) - set(assigned_candidate_ids))
    if unassigned:
        errors.append("候选需求尚未分配版本：" + ", ".join(unassigned))

    if errors:
        raise ProductPlanningError("PRD 质量门未通过：" + "；".join(errors))

    release_by_candidate_id = {
        candidate_id: release.release
        for release in draft.releases
        for candidate_id in release.requirement_candidate_ids
    }
    final_id_by_candidate_id = {
        candidate.candidate_id: f"REQ-{index:03d}"
        for index, candidate in enumerate(draft.requirements, start=1)
    }
    requirements: list[Requirement] = []
    for candidate in draft.requirements:
        findings = [
            finding_by_id[finding_id]
            for finding_id in candidate.source_finding_ids
        ]
        source_review_ids = list(
            dict.fromkeys(
                review_id
                for finding in findings
                for review_id in finding.supporting_review_ids
            )
        )
        invalid_review_ids = sorted(set(source_review_ids) - valid_review_ids)
        if invalid_review_ids:
            raise ProductPlanningError(
                "PRD 质量门未通过：Finding 引用了不存在的 Review："
                + ", ".join(invalid_review_ids)
            )
        requirements.append(
            Requirement(
                requirement_id=final_id_by_candidate_id[candidate.candidate_id],
                title=candidate.title,
                release=release_by_candidate_id[candidate.candidate_id],
                priority=calculate_requirement_priority(findings),
                description=candidate.description,
                source_finding_ids=candidate.source_finding_ids,
                source_review_ids=source_review_ids,
                in_scope=candidate.in_scope,
                out_of_scope=candidate.out_of_scope,
                acceptance_criteria=candidate.acceptance_criteria,
            )
        )

    releases = [
        ReleasePlanItem(
            release=release.release,
            objective=release.objective,
            requirement_ids=[
                final_id_by_candidate_id[candidate_id]
                for candidate_id in release.requirement_candidate_ids
            ],
            rationale=release.rationale,
            risks=release.risks,
        )
        for release in draft.releases
    ]
    return ProductPlanResult(
        prd_title=draft.prd_title,
        executive_summary=draft.executive_summary,
        releases=releases,
        requirements=requirements,
        deferred_findings=draft.deferred_findings,
        product_hypotheses=draft.product_hypotheses,
        limitations=[*finding_result.limitations, *draft.limitations],
    )


class ProductPlanningService:
    """让模型草拟规划，再由 Python 生成可信、可追溯的最终 PRD。"""

    def __init__(self, config: ModelConfig | None = None) -> None:
        self.config = config or ModelConfig.from_env()

    def generate(
        self,
        reviews: Sequence[Review],
        topic_result: TopicDiscoveryResult,
        finding_result: FindingGenerationResult,
        analysis_goal: str,
    ) -> ProductPlanResult:
        validate_planning_input(reviews, topic_result, finding_result)
        valid_review_ids = {review.review_id for review in reviews}
        quality = calculate_finding_quality(
            finding_result, topic_result, valid_review_ids
        )
        try:
            import instructor
            from openai import OpenAI

            client = instructor.from_openai(
                OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
            )
            draft = client.chat.completions.create(
                model=self.config.model,
                response_model=ProductPlanningDraft,
                messages=build_planning_messages(
                    reviews, finding_result, analysis_goal, quality
                ),
                max_retries=1,
                **build_model_request_options(self.config),
            )
        except ProductPlanningError:
            raise
        except Exception as error:
            raise ProductPlanningError(
                "模型调用或 PRD 结构化输出失败，本阶段已停止。"
                f"服务商返回：{safe_provider_error(error, self.config.api_key)}"
            ) from error
        return apply_planning_quality_gate(draft, finding_result, valid_review_ids)
