import unittest

from src.schemas import (
    Finding,
    FindingGenerationResult,
    ProductPlanResult,
    ReleasePlanItem,
    Requirement,
    Review,
    TestCaseCandidate,
    TestGenerationDraft,
)
from src.test_generation import (
    TestGenerationError,
    apply_test_quality_gate,
    calculate_traceability_quality,
    validate_plan_traceability,
)
from src.test_prompts import build_test_messages


class TestGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reviews = [
            Review(
                review_id="REV-001",
                source_id="SOURCE-001",
                content="I was charged after the trial without a reminder.",
                rating=1,
                source="test",
            ),
            Review(
                review_id="REV-002",
                source_id="SOURCE-002",
                content="Please warn me before the trial renews.",
                rating=2,
                source="test",
            ),
        ]
        self.finding_result = FindingGenerationResult(
            findings=[
                Finding(
                    finding_id="FIND-001",
                    title="试用自动续费提醒不足",
                    description="部分用户未感知到续费前提醒。",
                    source_topic_ids=["TOPIC-001"],
                    supporting_review_ids=["REV-001", "REV-002"],
                    severity="high",
                    confidence="medium",
                )
            ]
        )
        self.plan_result = ProductPlanResult(
            prd_title="订阅透明度 PRD",
            executive_summary="改善试用转付费前的信息透明度。",
            releases=[
                ReleasePlanItem(
                    release="V1.1",
                    objective="清晰告知续费信息",
                    requirement_ids=["REQ-001"],
                    rationale="降低意外扣费感受。",
                )
            ],
            requirements=[
                Requirement(
                    requirement_id="REQ-001",
                    title="试用结束前提醒",
                    release="V1.1",
                    priority="P1",
                    description="在试用结束前展示续费时间和价格。",
                    source_finding_ids=["FIND-001"],
                    source_review_ids=["REV-001", "REV-002"],
                    in_scope=["试用结束前提醒"],
                    out_of_scope=["修改套餐价格"],
                    acceptance_criteria=[
                        "试用用户在续费前看到结束时间和下一周期价格。"
                    ],
                )
            ],
        )

    def valid_draft(self) -> TestGenerationDraft:
        return TestGenerationDraft(
            test_cases=[
                TestCaseCandidate(
                    candidate_id=f"TCC-{index:03d}",
                    title=title,
                    requirement_id="REQ-001",
                    scenario_type=scenario_type,
                    preconditions=["用户处于免费试用期"],
                    steps=["进入续费提醒触发时点", "查看提醒内容"],
                    expected_results=[expected],
                )
                for index, (title, scenario_type, expected) in enumerate(
                    [
                        ("正常展示续费提醒", "normal", "显示结束时间和价格"),
                        ("提醒发送失败时可恢复", "negative", "记录失败且不显示成功状态"),
                        ("续费临界时点只提醒一次", "boundary", "临界时点不重复提醒"),
                    ],
                    start=1,
                )
            ]
        )

    def valid_ids(self) -> set[str]:
        return {review.review_id for review in self.reviews}

    def test_quality_gate_derives_ids_reviews_and_priority(self) -> None:
        result = apply_test_quality_gate(
            self.valid_draft(), self.plan_result, self.valid_ids()
        )

        self.assertEqual([case.test_case_id for case in result.test_cases], [
            "TC-001",
            "TC-002",
            "TC-003",
        ])
        self.assertEqual(result.test_cases[0].source_review_ids, ["REV-001", "REV-002"])
        self.assertEqual(result.test_cases[0].priority, "P1")

    def test_unknown_requirement_is_rejected(self) -> None:
        draft = self.valid_draft()
        draft.test_cases[0].requirement_id = "REQ-999"

        with self.assertRaisesRegex(TestGenerationError, "不存在的 Requirement"):
            apply_test_quality_gate(draft, self.plan_result, self.valid_ids())

    def test_p0_p1_requires_normal_negative_and_boundary(self) -> None:
        draft = self.valid_draft()
        draft.test_cases = draft.test_cases[:2]

        with self.assertRaisesRegex(TestGenerationError, "boundary"):
            apply_test_quality_gate(draft, self.plan_result, self.valid_ids())

    def test_p2_only_requires_normal_scenario(self) -> None:
        plan = self.plan_result.model_copy(deep=True)
        plan.requirements[0].priority = "P2"
        draft = self.valid_draft()
        draft.test_cases = draft.test_cases[:1]

        result = apply_test_quality_gate(draft, plan, self.valid_ids())

        self.assertEqual(len(result.test_cases), 1)

    def test_quality_gate_collapses_31_candidates_to_required_scenarios(self) -> None:
        base_cases = self.valid_draft().test_cases
        draft = TestGenerationDraft(
            test_cases=[
                base_cases[index % len(base_cases)].model_copy(
                    update={"candidate_id": f"TCC-{index + 1:03d}"}
                )
                for index in range(31)
            ]
        )

        result = apply_test_quality_gate(
            draft, self.plan_result, self.valid_ids()
        )

        self.assertEqual(len(result.test_cases), 3)
        self.assertEqual(
            {test_case.test_type for test_case in result.test_cases},
            {"normal", "negative", "boundary"},
        )
        self.assertTrue(
            any("移除 28 条" in limitation for limitation in result.limitations)
        )

    def test_upstream_requirement_reviews_must_match_finding(self) -> None:
        plan = self.plan_result.model_copy(deep=True)
        plan.requirements[0].source_review_ids = ["REV-001"]

        with self.assertRaisesRegex(TestGenerationError, "证据与来源 Finding 不一致"):
            validate_plan_traceability(self.reviews, self.finding_result, plan)

    def test_quality_metrics_show_complete_traceability(self) -> None:
        result = apply_test_quality_gate(
            self.valid_draft(), self.plan_result, self.valid_ids()
        )

        quality = calculate_traceability_quality(
            result, self.finding_result, self.plan_result, self.valid_ids()
        )

        self.assertEqual(quality.requirement_coverage, 100.0)
        self.assertEqual(quality.critical_scenario_coverage, 100.0)
        self.assertEqual(quality.review_traceability, 100.0)
        self.assertEqual(quality.invalid_references, 0)
        self.assertTrue(quality.quality_gate_passed)

    def test_quality_metrics_detect_tampered_test_case(self) -> None:
        result = apply_test_quality_gate(
            self.valid_draft(), self.plan_result, self.valid_ids()
        ).model_copy(deep=True)
        result.test_cases[0].source_review_ids = ["REV-999"]

        quality = calculate_traceability_quality(
            result, self.finding_result, self.plan_result, self.valid_ids()
        )

        self.assertGreater(quality.invalid_references, 0)
        self.assertLess(quality.review_traceability, 100.0)
        self.assertFalse(quality.quality_gate_passed)

    def test_quality_metrics_detect_broken_finding_to_review_chain(self) -> None:
        result = apply_test_quality_gate(
            self.valid_draft(), self.plan_result, self.valid_ids()
        )
        plan = self.plan_result.model_copy(deep=True)
        plan.requirements[0].source_review_ids = ["REV-001"]

        quality = calculate_traceability_quality(
            result, self.finding_result, plan, self.valid_ids()
        )

        self.assertGreater(quality.invalid_references, 0)
        self.assertFalse(quality.quality_gate_passed)

    def test_prompt_requires_critical_scenarios_without_review_ids_from_model(self) -> None:
        messages = build_test_messages(
            self.reviews, self.plan_result, "关注订阅透明度"
        )

        self.assertIn("normal、negative、boundary", messages[0]["content"])
        self.assertIn("不要填写 Review ID", messages[0]["content"])
        self.assertIn("REQ-001", messages[1]["content"])
        self.assertIn("关注订阅透明度", messages[1]["content"])
        self.assertIn("恰好输出 3 条测试用例", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
