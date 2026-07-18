import unittest

from pydantic import ValidationError

from src.finding_analysis import (
    FindingGenerationError,
    apply_finding_quality_gate,
    calculate_confidence,
)
from src.finding_prompts import FINDING_SYSTEM_PROMPT, build_finding_messages
from src.schemas import (
    AtomicInsight,
    DiscoveryCandidate,
    FindingCandidate,
    FindingDraft,
    Review,
    Topic,
    TopicDiscoveryResult,
)


class FindingAnalysisTests(unittest.TestCase):
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

    def valid_draft(self) -> FindingDraft:
        return FindingDraft(
            candidates=[
                FindingCandidate(
                    candidate_id="CAND-001",
                    title="登录过程发生崩溃",
                    description="部分用户在登录或验证后无法继续使用应用。",
                    supporting_insight_ids=["INSIGHT-001", "INSIGHT-002"],
                    conflicting_insight_ids=["INSIGHT-003"],
                    severity="high",
                ),
                FindingCandidate(
                    candidate_id="CAND-002",
                    title="搜索结果可能不完整",
                    description="一条评论提到搜索结果偶尔缺失。",
                    supporting_insight_ids=["INSIGHT-004"],
                    severity="medium",
                ),
            ]
        )

    def valid_ids(self) -> set[str]:
        return {review.review_id for review in self.reviews}

    def test_quality_gate_builds_finding_and_downgrades_small_sample(self) -> None:
        result = apply_finding_quality_gate(
            self.valid_draft(), self.topic_result, self.valid_ids()
        )

        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].finding_id, "FIND-001")
        self.assertEqual(result.findings[0].confidence, "medium")
        self.assertEqual(len(result.findings[0].supporting_review_ids), 2)
        self.assertEqual(result.discovery_items[0].discovery_id, "DISC-001")
        self.assertIn("只有 1 条", result.discovery_items[0].reason)

    def test_hallucinated_review_id_is_rejected(self) -> None:
        draft = self.valid_draft()
        draft.candidates[0].supporting_insight_ids[0] = "INSIGHT-999"

        with self.assertRaisesRegex(FindingGenerationError, "不存在的 Insight"):
            apply_finding_quality_gate(draft, self.topic_result, self.valid_ids())

    def test_positive_review_cannot_be_supporting_evidence(self) -> None:
        draft = self.valid_draft()
        draft.candidates[0].supporting_insight_ids = [
            "INSIGHT-001",
            "INSIGHT-003",
        ]
        draft.candidates[0].conflicting_insight_ids = []

        with self.assertRaisesRegex(FindingGenerationError, "不是 negative"):
            apply_finding_quality_gate(draft, self.topic_result, self.valid_ids())

    def test_uncovered_topic_is_rejected(self) -> None:
        draft = self.valid_draft()
        draft.candidates = [draft.candidates[0]]

        with self.assertRaisesRegex(FindingGenerationError, "未被分析"):
            apply_finding_quality_gate(draft, self.topic_result, self.valid_ids())

    def test_explicit_discovery_candidate_covers_topic(self) -> None:
        draft = FindingDraft(
            candidates=[self.valid_draft().candidates[0]],
            discovery_candidates=[
                DiscoveryCandidate(
                    title="搜索结果完整性待验证",
                    reason="当前只有一条 mixed 评论。",
                    insight_ids=["INSIGHT-004"],
                )
            ],
        )

        result = apply_finding_quality_gate(
            draft, self.topic_result, self.valid_ids()
        )

        self.assertEqual(len(result.discovery_items), 1)
        self.assertEqual(result.discovery_items[0].review_ids, ["REV-004"])

    def test_confidence_is_calculated_from_counts(self) -> None:
        self.assertEqual(calculate_confidence(5, 1, 8), "high")
        self.assertEqual(calculate_confidence(2, 0, 4), "medium")
        self.assertEqual(calculate_confidence(2, 2, 4), "low")

    def test_prompt_forbids_model_generated_counts_and_prd(self) -> None:
        messages = build_finding_messages(
            self.reviews, self.topic_result, "关注稳定性"
        )

        self.assertIn("不要输出支持数量和置信度", FINDING_SYSTEM_PROMPT)
        self.assertIn("不生成版本规划", FINDING_SYSTEM_PROMPT)
        self.assertIn("REV-001", messages[1]["content"])
        self.assertIn("关注稳定性", messages[1]["content"])

    def test_same_insight_cannot_feed_multiple_candidates(self) -> None:
        candidate = self.valid_draft().candidates[0]

        with self.assertRaisesRegex(ValidationError, "不能被多个"):
            FindingDraft(
                candidates=[
                    candidate,
                    candidate.model_copy(
                        update={"candidate_id": "CAND-999"}
                    ),
                ]
            )


if __name__ == "__main__":
    unittest.main()
