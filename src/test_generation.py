"""测试用例草拟、端到端追溯校验和覆盖率计算。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.config import ModelConfig
from src.schemas import (
    FindingGenerationResult,
    ProductPlanResult,
    Requirement,
    Review,
    TestCase,
    TestGenerationDraft,
    TestGenerationResult,
)
from src.test_prompts import build_test_messages
from src.topic_discovery import build_model_request_options, safe_provider_error


class TestGenerationError(RuntimeError):
    """测试用例无法在完整追溯约束下安全生成。"""


@dataclass(frozen=True)
class TraceabilityQualityReport:
    """由 Python 复算的测试覆盖与端到端追溯指标。"""

    requirement_coverage: float
    critical_scenario_coverage: float
    review_traceability: float
    invalid_references: int
    covered_requirement_count: int
    requirement_count: int
    covered_critical_scenarios: int
    required_critical_scenarios: int
    traceable_review_count: int
    referenced_review_count: int

    @property
    def quality_gate_passed(self) -> bool:
        return (
            self.requirement_coverage == 100.0
            and self.critical_scenario_coverage == 100.0
            and self.review_traceability == 100.0
            and self.invalid_references == 0
        )


def _percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 100.0
    return numerator / denominator * 100


def _required_scenarios(requirement: Requirement) -> set[str]:
    if requirement.priority in {"P0", "P1"}:
        return {"normal", "negative", "boundary"}
    return {"normal"}


def validate_plan_traceability(
    reviews: Sequence[Review],
    finding_result: FindingGenerationResult,
    plan_result: ProductPlanResult,
) -> None:
    """在模型调用前确认 Requirement 能完整回到 Finding 与 Review。"""
    valid_review_ids = {review.review_id for review in reviews}
    finding_by_id = {
        finding.finding_id: finding for finding in finding_result.findings
    }
    requirement_ids = [item.requirement_id for item in plan_result.requirements]
    errors: list[str] = []
    if not requirement_ids:
        errors.append("没有可生成测试的 Requirement")
    if len(requirement_ids) != len(set(requirement_ids)):
        errors.append("Requirement ID 不得重复")

    for requirement in plan_result.requirements:
        source_finding_ids = set(requirement.source_finding_ids)
        invalid_finding_ids = sorted(source_finding_ids - set(finding_by_id))
        if invalid_finding_ids:
            errors.append(
                f"{requirement.requirement_id} 引用了不存在的 Finding："
                + ", ".join(invalid_finding_ids)
            )
            continue
        expected_review_ids = {
            review_id
            for finding_id in requirement.source_finding_ids
            for review_id in finding_by_id[finding_id].supporting_review_ids
        }
        actual_review_ids = set(requirement.source_review_ids)
        if actual_review_ids != expected_review_ids:
            errors.append(
                f"{requirement.requirement_id} 的 Review 证据与来源 Finding 不一致"
            )
        invalid_review_ids = sorted(actual_review_ids - valid_review_ids)
        if invalid_review_ids:
            errors.append(
                f"{requirement.requirement_id} 引用了不存在的 Review："
                + ", ".join(invalid_review_ids)
            )
    if errors:
        raise TestGenerationError("上游追溯校验未通过：" + "；".join(errors))


def apply_test_quality_gate(
    draft: TestGenerationDraft,
    plan_result: ProductPlanResult,
    valid_review_ids: set[str],
) -> TestGenerationResult:
    """校验场景覆盖，并从 Requirement 派生最终测试证据与 ID。"""
    requirement_by_id = {
        requirement.requirement_id: requirement
        for requirement in plan_result.requirements
    }
    errors: list[str] = []
    selected_candidates = []
    selected_slots: set[tuple[str, str]] = set()
    redundant_candidate_count = 0
    for candidate in draft.test_cases:
        requirement = requirement_by_id.get(candidate.requirement_id)
        if requirement is None:
            errors.append(
                f"{candidate.candidate_id} 引用了不存在的 Requirement："
                f"{candidate.requirement_id}"
            )
            continue
        slot = (candidate.requirement_id, candidate.scenario_type)
        if (
            candidate.scenario_type not in _required_scenarios(requirement)
            or slot in selected_slots
        ):
            redundant_candidate_count += 1
            continue
        selected_slots.add(slot)
        selected_candidates.append(candidate)

    for requirement_id, requirement in requirement_by_id.items():
        missing = sorted(
            _required_scenarios(requirement)
            - {
                scenario
                for selected_requirement_id, scenario in selected_slots
                if selected_requirement_id == requirement_id
            }
        )
        if missing:
            errors.append(
                f"{requirement_id} 缺少测试场景：" + ", ".join(missing)
            )
        invalid_review_ids = sorted(
            set(requirement.source_review_ids) - valid_review_ids
        )
        if invalid_review_ids:
            errors.append(
                f"{requirement_id} 引用了不存在的 Review："
                + ", ".join(invalid_review_ids)
            )
    if errors:
        raise TestGenerationError("测试质量门未通过：" + "；".join(errors))

    test_cases = [
        TestCase(
            test_case_id=f"TC-{index:03d}",
            title=candidate.title,
            requirement_id=candidate.requirement_id,
            source_review_ids=requirement_by_id[
                candidate.requirement_id
            ].source_review_ids,
            priority=requirement_by_id[candidate.requirement_id].priority,
            test_type=candidate.scenario_type,
            preconditions=candidate.preconditions,
            steps=candidate.steps,
            expected_results=candidate.expected_results,
        )
        for index, candidate in enumerate(selected_candidates, start=1)
    ]
    limitations = [*plan_result.limitations, *draft.limitations]
    if redundant_candidate_count:
        limitations.append(
            f"Python 已移除 {redundant_candidate_count} 条重复或非必需测试候选；"
            "每个 Requirement 的必需场景只保留一条。"
        )
    return TestGenerationResult(
        test_cases=test_cases,
        limitations=limitations,
    )


def calculate_traceability_quality(
    result: TestGenerationResult,
    finding_result: FindingGenerationResult,
    plan_result: ProductPlanResult,
    valid_review_ids: set[str],
) -> TraceabilityQualityReport:
    """复算 Requirement 覆盖、关键场景覆盖和 Review 可追溯性。"""
    requirement_by_id = {
        requirement.requirement_id: requirement
        for requirement in plan_result.requirements
    }
    finding_by_id = {
        finding.finding_id: finding for finding in finding_result.findings
    }
    finding_ids = set(finding_by_id)
    covered_requirement_ids: set[str] = set()
    covered_scenario_slots: set[tuple[str, str]] = set()
    required_scenario_slots = {
        (requirement.requirement_id, scenario)
        for requirement in plan_result.requirements
        for scenario in _required_scenarios(requirement)
    }
    referenced_review_ids: set[str] = set()
    invalid_references = 0

    for requirement in plan_result.requirements:
        invalid_finding_ids = set(requirement.source_finding_ids) - finding_ids
        if invalid_finding_ids:
            invalid_references += 1
        else:
            expected_review_ids = {
                review_id
                for finding_id in requirement.source_finding_ids
                for review_id in finding_by_id[finding_id].supporting_review_ids
            }
            if set(requirement.source_review_ids) != expected_review_ids:
                invalid_references += 1
        if set(requirement.source_review_ids) - valid_review_ids:
            invalid_references += 1

    for test_case in result.test_cases:
        referenced_review_ids.update(test_case.source_review_ids)
        requirement = requirement_by_id.get(test_case.requirement_id)
        if requirement is None:
            invalid_references += 1
            continue
        covered_requirement_ids.add(test_case.requirement_id)
        slot = (test_case.requirement_id, test_case.test_type)
        if slot in required_scenario_slots:
            covered_scenario_slots.add(slot)
        if set(test_case.source_review_ids) != set(requirement.source_review_ids):
            invalid_references += 1
        if test_case.priority != requirement.priority:
            invalid_references += 1

    traceable_review_ids = referenced_review_ids & valid_review_ids
    return TraceabilityQualityReport(
        requirement_coverage=_percent(
            len(covered_requirement_ids), len(requirement_by_id)
        ),
        critical_scenario_coverage=_percent(
            len(covered_scenario_slots), len(required_scenario_slots)
        ),
        review_traceability=_percent(
            len(traceable_review_ids), len(referenced_review_ids)
        ),
        invalid_references=invalid_references,
        covered_requirement_count=len(covered_requirement_ids),
        requirement_count=len(requirement_by_id),
        covered_critical_scenarios=len(covered_scenario_slots),
        required_critical_scenarios=len(required_scenario_slots),
        traceable_review_count=len(traceable_review_ids),
        referenced_review_count=len(referenced_review_ids),
    )


class TestGenerationService:
    """通过模型草拟用例，再由 Python 建立完整可追溯结果。"""

    def __init__(self, config: ModelConfig | None = None) -> None:
        self.config = config or ModelConfig.from_env()

    def generate(
        self,
        reviews: Sequence[Review],
        finding_result: FindingGenerationResult,
        plan_result: ProductPlanResult,
        analysis_goal: str,
    ) -> TestGenerationResult:
        validate_plan_traceability(reviews, finding_result, plan_result)
        try:
            import instructor
            from openai import OpenAI

            client = instructor.from_openai(
                OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
            )
            draft = client.chat.completions.create(
                model=self.config.model,
                response_model=TestGenerationDraft,
                messages=build_test_messages(reviews, plan_result, analysis_goal),
                max_retries=1,
                **build_model_request_options(self.config),
            )
        except TestGenerationError:
            raise
        except Exception as error:
            raise TestGenerationError(
                "模型调用或测试用例结构化输出失败，本阶段已停止。"
                f"服务商返回：{safe_provider_error(error, self.config.api_key)}"
            ) from error
        return apply_test_quality_gate(
            draft, plan_result, {review.review_id for review in reviews}
        )
