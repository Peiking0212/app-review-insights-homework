import unittest

from src.finding_analysis import calculate_finding_quality
from src.planning_prompts import build_planning_messages
from src.product_planning import (
    ProductPlanningError,
    apply_planning_quality_gate,
    calculate_requirement_priority,
    validate_planning_input,
)
from src.schemas import (
    AtomicInsight,
    DeferredFinding,
    DiscoveryItem,
    Finding,
    FindingGenerationResult,
    ProductHypothesis,
    ProductPlanningDraft,
    ReleaseCandidate,
    RequirementCandidate,
    Review,
    Topic,
    TopicDiscoveryResult,
)


class ProductPlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reviews = [
            Review(
                review_id=f"REV-{index:03d}",
                source_id=f"SOURCE-{index:03d}",
                content=content,
                rating=rating,
                source="test",
            )
            for index, (content, rating) in enumerate(
                [
                    ("Login crashes after verification.", 1),
                    ("The app closes whenever I sign in.", 2),
                    ("Login works reliably for me.", 5),
                    ("Search results sometimes look incomplete.", 3),
                ],
                start=1,
            )
        ]
        self.topic_result = TopicDiscoveryResult(
            insights=[
                AtomicInsight(
                    insight_id="INSIGHT-001",
                    review_id="REV-001",
                    statement="登录验证后崩溃",
                    sentiment="negative",
                ),
                AtomicInsight(
                    insight_id="INSIGHT-002",
                    review_id="REV-002",
                    statement="登录时应用关闭",
                    sentiment="negative",
                ),
                AtomicInsight(
                    insight_id="INSIGHT-003",
                    review_id="REV-003",
                    statement="登录体验稳定",
                    sentiment="positive",
                ),
                AtomicInsight(
                    insight_id="INSIGHT-004",
                    review_id="REV-004",
                    statement="搜索结果偶尔不完整",
                    sentiment="mixed",
                ),
            ],
            topics=[
                Topic(
                    topic_id="TOPIC-001",
                    name="登录稳定性",
                    description="登录过程的稳定体验。",
                    insight_ids=["INSIGHT-001", "INSIGHT-002", "INSIGHT-003"],
                    representative_review_ids=["REV-001", "REV-003"],
                ),
                Topic(
                    topic_id="TOPIC-002",
                    name="搜索完整性",
                    description="搜索结果是否完整。",
                    insight_ids=["INSIGHT-004"],
                    representative_review_ids=["REV-004"],
                ),
            ],
        )
        self.finding_result = FindingGenerationResult(
            findings=[
                Finding(
                    finding_id="FIND-001",
                    title="登录过程发生崩溃",
                    description="部分用户在登录或验证后无法继续使用。",
                    source_topic_ids=["TOPIC-001"],
                    supporting_review_ids=["REV-001", "REV-002"],
                    conflicting_review_ids=["REV-003"],
                    severity="high",
                    confidence="medium",
                )
            ],
            discovery_items=[
                DiscoveryItem(
                    discovery_id="DISC-001",
                    title="搜索结果完整性待验证",
                    reason="只有一条评论。",
                    source_topic_ids=["TOPIC-002"],
                    review_ids=["REV-004"],
                )
            ],
        )

    def valid_draft(self) -> ProductPlanningDraft:
        return ProductPlanningDraft(
            prd_title="登录稳定性改进 PRD",
            executive_summary="优先修复有两条评论支持的登录崩溃问题。",
            requirements=[
                RequirementCandidate(
                    candidate_id="REQC-001",
                    title="保证登录流程可完成",
                    description="修复验证后异常退出，向用户呈现可恢复结果。",
                    source_finding_ids=["FIND-001"],
                    in_scope=["登录验证后的异常处理"],
                    out_of_scope=["搜索体验改版"],
                    acceptance_criteria=[
                        "Given 用户提交有效登录信息，When 验证完成，Then 应用保持运行并进入结果页。"
                    ],
                )
            ],
            releases=[
                ReleaseCandidate(
                    release="V1.1",
                    objective="恢复登录主路径的可用性",
                    requirement_candidate_ids=["REQC-001"],
                    rationale="登录失败会阻断用户使用核心功能。",
                    risks=["需覆盖不同登录方式"],
                )
            ],
        )

    def valid_ids(self) -> set[str]:
        return {review.review_id for review in self.reviews}

    def test_quality_gate_derives_review_ids_priority_and_final_ids(self) -> None:
        result = apply_planning_quality_gate(
            self.valid_draft(), self.finding_result, self.valid_ids()
        )

        requirement = result.requirements[0]
        self.assertEqual(requirement.requirement_id, "REQ-001")
        self.assertEqual(requirement.priority, "P1")
        self.assertEqual(requirement.source_review_ids, ["REV-001", "REV-002"])
        self.assertEqual(result.releases[0].requirement_ids, ["REQ-001"])

    def test_hallucinated_finding_is_rejected(self) -> None:
        draft = self.valid_draft()
        draft.requirements[0].source_finding_ids = ["FIND-999"]

        with self.assertRaisesRegex(ProductPlanningError, "不存在的 Finding"):
            apply_planning_quality_gate(draft, self.finding_result, self.valid_ids())

    def test_finding_must_be_addressed_or_deferred(self) -> None:
        draft = self.valid_draft()
        draft.requirements[0].source_finding_ids = []

        with self.assertRaisesRegex(ProductPlanningError, "未被处理"):
            apply_planning_quality_gate(draft, self.finding_result, self.valid_ids())

    def test_finding_cannot_be_addressed_and_deferred(self) -> None:
        draft = self.valid_draft()
        draft.deferred_findings = [
            DeferredFinding(
                finding_id="FIND-001",
                reason="暂缓",
                next_validation="收集更多登录日志",
            )
        ]

        with self.assertRaisesRegex(ProductPlanningError, "同时进入"):
            apply_planning_quality_gate(draft, self.finding_result, self.valid_ids())

    def test_requirement_must_be_assigned_to_exactly_one_release(self) -> None:
        draft = self.valid_draft()
        draft.releases.append(
            draft.releases[0].model_copy(update={"release": "V1.2"})
        )

        with self.assertRaisesRegex(ProductPlanningError, "只能进入一个版本"):
            apply_planning_quality_gate(draft, self.finding_result, self.valid_ids())

    def test_low_confidence_downgrades_priority(self) -> None:
        finding = self.finding_result.findings[0].model_copy(
            update={"severity": "critical", "confidence": "low"}
        )

        self.assertEqual(calculate_requirement_priority([finding]), "P1")

    def test_hypothesis_remains_separate_from_requirements(self) -> None:
        draft = self.valid_draft()
        draft.product_hypotheses = [
            ProductHypothesis(
                hypothesis_id="HYP-001",
                title="增加无密码登录",
                rationale="可能减少登录摩擦，但当前评论没有直接证据。",
                validation_plan="先做可用性访谈，不进入承诺版本。",
            )
        ]

        result = apply_planning_quality_gate(
            draft, self.finding_result, self.valid_ids()
        )

        self.assertEqual(len(result.requirements), 1)
        self.assertEqual(result.product_hypotheses[0].hypothesis_id, "HYP-001")

    def test_invalid_groundedness_stops_before_model_call(self) -> None:
        invalid_result = self.finding_result.model_copy(deep=True)
        invalid_result.findings[0].supporting_review_ids[0] = "REV-999"

        with self.assertRaisesRegex(ProductPlanningError, "Quality Gate"):
            validate_planning_input(
                self.reviews, self.topic_result, invalid_result
            )

    def test_prompt_excludes_discovery_and_forbids_padding(self) -> None:
        quality = calculate_finding_quality(
            self.finding_result, self.topic_result, self.valid_ids()
        )
        messages = build_planning_messages(
            self.reviews, self.finding_result, "关注稳定性", quality
        )

        self.assertIn("不得为了数量凑数", messages[0]["content"])
        self.assertIn("绝不能转成正式需求", messages[0]["content"])
        self.assertIn("DISC-001", messages[1]["content"])
        self.assertIn("关注稳定性", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
