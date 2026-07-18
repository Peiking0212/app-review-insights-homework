import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.analysis_cache import (
    AnalysisCacheError,
    create_snapshot,
    load_snapshot,
    promote_complete_demo,
    save_snapshot,
)
from src.schemas import (
    AtomicInsight,
    Finding,
    FindingGenerationResult,
    ProductPlanResult,
    ReleasePlanItem,
    Requirement,
    TestCase,
    TestGenerationResult,
    Topic,
    TopicDiscoveryResult,
)


class AnalysisCacheTests(unittest.TestCase):
    def complete_snapshot(self):
        topic_result = TopicDiscoveryResult(
            insights=[
                AtomicInsight(
                    insight_id="INSIGHT-001",
                    review_id="REV-AS-001",
                    statement="订阅提醒不清楚",
                    sentiment="negative",
                )
            ],
            topics=[
                Topic(
                    topic_id="TOPIC-001",
                    name="订阅透明度",
                    description="用户难以理解续费信息。",
                    insight_ids=["INSIGHT-001"],
                    representative_review_ids=["REV-AS-001"],
                )
            ],
        )
        finding_result = FindingGenerationResult(
            findings=[
                Finding(
                    finding_id="FIND-001",
                    title="续费提醒不清楚",
                    description="用户在续费前缺少明确提醒。",
                    source_topic_ids=["TOPIC-001"],
                    supporting_review_ids=["REV-AS-001"],
                    severity="high",
                    confidence="low",
                )
            ]
        )
        planning_result = ProductPlanResult(
            prd_title="订阅透明度 PRD",
            executive_summary="改善续费提醒。",
            releases=[
                ReleasePlanItem(
                    release="V1.1",
                    objective="改善续费提醒",
                    requirement_ids=["REQ-001"],
                    rationale="回应真实评论。",
                )
            ],
            requirements=[
                Requirement(
                    requirement_id="REQ-001",
                    title="续费前提醒",
                    release="V1.1",
                    priority="P1",
                    description="续费前展示时间和价格。",
                    source_finding_ids=["FIND-001"],
                    source_review_ids=["REV-AS-001"],
                    in_scope=["续费提醒"],
                    acceptance_criteria=["用户能够看到续费时间和价格。"],
                )
            ],
        )
        test_result = TestGenerationResult(
            test_cases=[
                TestCase(
                    test_case_id="TC-001",
                    title="显示续费提醒",
                    requirement_id="REQ-001",
                    source_review_ids=["REV-AS-001"],
                    priority="P1",
                    test_type="normal",
                    steps=["进入续费提醒时点"],
                    expected_results=["显示时间和价格"],
                )
            ]
        )
        return create_snapshot(
            source_type="app_store_us",
            analysis_goal="关注订阅透明度",
            analysis_fingerprint="a" * 64,
            model_name="test-model",
            raw_reviews=[
                {
                    "review_id": "REV-AS-001",
                    "source_id": "001",
                    "content": "The renewal was not clear.",
                    "rating": 1,
                    "storefront": "us",
                    "source": "apple_public_rss_us",
                }
            ],
            cleaning_report={"raw_count": 1, "cleaned_count": 1},
            collection_report={
                "app_id": "839285684",
                "app_name": "Workout for Women",
                "storefront": "us",
                "canonical_url": "https://apps.apple.com/us/app/id839285684",
                "collected_at": "2026-07-18T00:00:00+00:00",
                "requested_review_count": 1,
                "collected_review_count": 1,
                "pages_attempted": 1,
                "pages_succeeded": 1,
                "empty_pages": [],
                "duplicates_removed": 0,
                "malformed_removed": 0,
                "source_urls": ["https://example.test/feed"],
                "limitations": [],
            },
            topic_result=topic_result.model_dump(mode="json"),
            finding_result=finding_result.model_dump(mode="json"),
            planning_result=planning_result.model_dump(mode="json"),
            test_result=test_result.model_dump(mode="json"),
            now=datetime(2026, 7, 18, tzinfo=timezone.utc),
        )

    def test_complete_real_snapshot_round_trips(self) -> None:
        snapshot = self.complete_snapshot()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.json"
            save_snapshot(snapshot, path)
            loaded = load_snapshot(path)

        self.assertTrue(loaded.is_complete_demo)
        self.assertEqual(loaded.completed_stage, "test")
        self.assertEqual(loaded.topic_result.topics[0].topic_id, "TOPIC-001")
        self.assertNotIn("api_key", snapshot.model_dump_json().lower())

    def test_promote_rejects_incomplete_snapshot(self) -> None:
        snapshot = self.complete_snapshot().model_copy(
            update={"test_result": None}
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AnalysisCacheError, "完整"):
                promote_complete_demo(snapshot, Path(directory) / "demo.json")

    def test_downstream_stage_without_upstream_is_rejected(self) -> None:
        payload = self.complete_snapshot().model_dump(mode="json")
        payload["topic_result"] = None

        with self.assertRaisesRegex(ValueError, "缺少上游 Topic"):
            type(self.complete_snapshot()).model_validate(payload)

    def test_corrupted_snapshot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{broken", encoding="utf-8")

            with self.assertRaisesRegex(AnalysisCacheError, "校验失败"):
                load_snapshot(path)


if __name__ == "__main__":
    unittest.main()
