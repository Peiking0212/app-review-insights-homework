import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from src.finding_analysis import (
    FindingGenerationError,
    FindingAnalysisService,
    IncompleteFindingCoverageError,
    apply_finding_quality_gate,
    calculate_confidence,
    calculate_finding_quality,
    merge_finding_repair,
)
from src.config import ModelConfig
from src.finding_prompts import (
    FINDING_REPAIR_SYSTEM_PROMPT,
    FINDING_SYSTEM_PROMPT,
    build_finding_messages,
    build_finding_repair_messages,
)
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

        with self.assertRaisesRegex(IncompleteFindingCoverageError, "未被分析"):
            apply_finding_quality_gate(draft, self.topic_result, self.valid_ids())

    def test_repair_prompt_only_contains_missing_topic_evidence(self) -> None:
        messages = build_finding_repair_messages(
            self.reviews, self.topic_result, ["TOPIC-002"], "关注稳定性"
        )

        self.assertIn("只分析 missing_topics", FINDING_REPAIR_SYSTEM_PROMPT)
        self.assertIn("TOPIC-002", messages[1]["content"])
        self.assertIn("INSIGHT-004", messages[1]["content"])
        self.assertIn("REV-004", messages[1]["content"])
        self.assertNotIn("TOPIC-001", messages[1]["content"])
        self.assertNotIn("INSIGHT-001", messages[1]["content"])

    def test_python_merges_missing_topic_repair(self) -> None:
        original = FindingDraft(candidates=[self.valid_draft().candidates[0]])
        repair = FindingDraft(
            discovery_candidates=[
                DiscoveryCandidate(
                    title="搜索完整性待验证",
                    reason="当前只有一条 mixed 评论。",
                    insight_ids=["INSIGHT-004"],
                )
            ]
        )

        merged = merge_finding_repair(
            original, repair, self.topic_result, ["TOPIC-002"]
        )
        result = apply_finding_quality_gate(
            merged, self.topic_result, self.valid_ids()
        )

        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.discovery_items[0].source_topic_ids, ["TOPIC-002"])
        self.assertTrue(
            any("有限补分析覆盖了 1 个" in item for item in result.limitations)
        )

    def test_repair_rejects_insight_from_already_covered_topic(self) -> None:
        original = FindingDraft(candidates=[self.valid_draft().candidates[0]])
        repair = FindingDraft(
            discovery_candidates=[
                DiscoveryCandidate(
                    title="错误重复分析",
                    reason="错误引用已覆盖主题。",
                    insight_ids=["INSIGHT-001"],
                )
            ]
        )

        with self.assertRaisesRegex(FindingGenerationError, "非遗漏 Topic"):
            merge_finding_repair(
                original, repair, self.topic_result, ["TOPIC-002"]
            )

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

    def test_quality_metrics_are_recalculated_from_evidence(self) -> None:
        result = apply_finding_quality_gate(
            self.valid_draft(), self.topic_result, self.valid_ids()
        )

        quality = calculate_finding_quality(
            result, self.topic_result, self.valid_ids()
        )

        self.assertEqual(quality.evidence_coverage, 100.0)
        self.assertEqual(quality.review_traceability, 100.0)
        self.assertEqual(quality.unsupported_claims, 0)
        self.assertEqual(quality.conflict_evidence, 1)
        self.assertEqual(quality.covered_review_count, 4)
        self.assertTrue(quality.quality_gate_passed)

    def test_quality_coverage_drops_when_discovery_is_omitted(self) -> None:
        result = apply_finding_quality_gate(
            self.valid_draft(), self.topic_result, self.valid_ids()
        ).model_copy(update={"discovery_items": []})

        quality = calculate_finding_quality(
            result, self.topic_result, self.valid_ids()
        )

        self.assertEqual(quality.evidence_coverage, 75.0)
        self.assertEqual(quality.review_traceability, 100.0)

    def test_quality_report_detects_unsupported_claim(self) -> None:
        result = apply_finding_quality_gate(
            self.valid_draft(), self.topic_result, self.valid_ids()
        ).model_copy(deep=True)
        result.findings[0].source_topic_ids = ["TOPIC-999"]
        result.findings[0].supporting_review_ids[0] = "REV-999"

        quality = calculate_finding_quality(
            result, self.topic_result, self.valid_ids()
        )

        self.assertEqual(quality.unsupported_claims, 1)
        self.assertLess(quality.review_traceability, 100.0)
        self.assertFalse(quality.quality_gate_passed)

    def test_prompt_forbids_model_generated_counts_and_prd(self) -> None:
        messages = build_finding_messages(
            self.reviews, self.topic_result, "关注稳定性"
        )

        self.assertIn("不要输出支持数量和置信度", FINDING_SYSTEM_PROMPT)
        self.assertIn(
            "每个 Insight ID 在全部 candidates 和 discovery_candidates 中最多出现一次",
            FINDING_SYSTEM_PROMPT,
        )
        self.assertIn("合并语义重叠的问题", FINDING_SYSTEM_PROMPT)
        self.assertIn("不生成版本规划", FINDING_SYSTEM_PROMPT)
        self.assertIn("输出前必须执行以下硬性自检", messages[1]["content"])
        self.assertIn(
            "conflicting_insight_ids 已经算作 Topic 被覆盖",
            messages[1]["content"],
        )
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

    def test_same_insight_cannot_feed_finding_and_discovery(self) -> None:
        candidate = self.valid_draft().candidates[0]

        with self.assertRaisesRegex(ValidationError, "INSIGHT-001"):
            FindingDraft(
                candidates=[candidate],
                discovery_candidates=[
                    DiscoveryCandidate(
                        title="登录问题仍需探索",
                        reason="需要更多样本。",
                        insight_ids=["INSIGHT-001"],
                    )
                ],
            )

    def test_service_repairs_missing_topic_once(self) -> None:
        config = ModelConfig(
            api_key="local-test-key",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
        )
        original = FindingDraft(candidates=[self.valid_draft().candidates[0]])
        repair = FindingDraft(
            discovery_candidates=[
                DiscoveryCandidate(
                    title="搜索完整性待验证",
                    reason="当前只有一条 mixed 评论。",
                    insight_ids=["INSIGHT-004"],
                )
            ]
        )
        structured_client = MagicMock()
        structured_client.chat.completions.create.side_effect = [original, repair]

        with patch("openai.OpenAI"), patch(
            "instructor.from_openai", return_value=structured_client
        ):
            result = FindingAnalysisService(config).generate(
                self.reviews, self.topic_result, "关注稳定性"
            )

        self.assertEqual(structured_client.chat.completions.create.call_count, 2)
        repair_call = structured_client.chat.completions.create.call_args_list[1]
        self.assertIn("TOPIC-002", repair_call.kwargs["messages"][1]["content"])
        self.assertNotIn("TOPIC-001", repair_call.kwargs["messages"][1]["content"])
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(len(result.discovery_items), 1)


if __name__ == "__main__":
    unittest.main()
