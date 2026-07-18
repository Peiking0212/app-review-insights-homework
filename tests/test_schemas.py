import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.schemas import (
    AtomicInsight,
    Finding,
    Requirement,
    Review,
    TestCase,
    Topic,
    TopicDiscoveryResult,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]


class TraceableSchemaTests(unittest.TestCase):
    def test_all_sample_reviews_match_review_schema(self) -> None:
        with (PROJECT_DIR / "data" / "sample_reviews.json").open(
            "r", encoding="utf-8"
        ) as file:
            reviews = json.load(file)

        parsed = [Review.model_validate(review) for review in reviews]

        self.assertEqual(len(parsed), 6)
        self.assertTrue(all(review.storefront == "us" for review in parsed))

    def test_complete_traceability_chain_is_valid(self) -> None:
        review = Review(
            review_id="REV-001",
            source_id="SOURCE-001",
            content="The renewal reminder was unclear.",
            rating=2,
            storefront="us",
            source="illustrative_sample",
        )
        topic = Topic(
            topic_id="TOPIC-001",
            name="Renewal communication",
            description="Feedback about renewal information.",
            insight_ids=["INSIGHT-001"],
            representative_review_ids=[review.review_id],
        )
        finding = Finding(
            finding_id="FIND-001",
            title="Renewal timing is unclear",
            description="Users cannot identify the renewal time.",
            source_topic_ids=[topic.topic_id],
            supporting_review_ids=[review.review_id],
            severity="high",
            confidence="medium",
        )
        requirement = Requirement(
            requirement_id="REQ-001",
            title="Show renewal time",
            release="V1.1",
            priority="P0",
            description="Display the renewal time before confirmation.",
            source_finding_ids=[finding.finding_id],
            source_review_ids=[review.review_id],
            in_scope=["Show renewal date and price"],
            acceptance_criteria=["Renewal date is visible before confirmation"],
        )
        test_case = TestCase(
            test_case_id="TC-001",
            title="Renewal information is visible",
            requirement_id=requirement.requirement_id,
            source_review_ids=[review.review_id],
            priority="P0",
            test_type="functional",
            steps=["Open the subscription confirmation screen"],
            expected_results=["Renewal date and price are visible"],
        )

        self.assertEqual(test_case.requirement_id, "REQ-001")

    def test_review_rejects_invalid_rating(self) -> None:
        with self.assertRaises(ValidationError):
            Review(
                review_id="REV-001",
                source_id="SOURCE-001",
                content="Invalid rating",
                rating=6,
                source="csv",
            )

    def test_review_rejects_non_us_storefront(self) -> None:
        with self.assertRaises(ValidationError):
            Review(
                review_id="REV-001",
                source_id="SOURCE-001",
                content="Wrong storefront",
                rating=3,
                storefront="cn",
                source="csv",
            )

    def test_requirement_requires_review_and_finding_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            Requirement(
                requirement_id="REQ-001",
                title="Unsupported requirement",
                release="V1.1",
                priority="P1",
                description="This requirement has no evidence.",
                source_finding_ids=[],
                source_review_ids=[],
                in_scope=["Something"],
                acceptance_criteria=["Something happens"],
            )

    def test_finding_rejects_overlapping_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            Finding(
                finding_id="FIND-001",
                title="Conflicting evidence",
                description="The same review appears in both lists.",
                source_topic_ids=["TOPIC-001"],
                supporting_review_ids=["REV-001"],
                conflicting_review_ids=["REV-001"],
                severity="medium",
                confidence="low",
            )

    def test_reference_ids_require_expected_prefix(self) -> None:
        with self.assertRaises(ValidationError):
            Topic(
                topic_id="TOPIC-001",
                name="Invalid reference",
                description="Uses a finding ID as a review ID.",
                insight_ids=["INSIGHT-001"],
                representative_review_ids=["FIND-001"],
            )

    def test_topic_result_allows_distinct_insights_from_one_review(self) -> None:
        result = TopicDiscoveryResult(
            insights=[
                AtomicInsight(
                    insight_id="INSIGHT-001",
                    review_id="REV-001",
                    statement="订单缺少商品",
                    sentiment="negative",
                ),
                AtomicInsight(
                    insight_id="INSIGHT-002",
                    review_id="REV-001",
                    statement="无法联系客户支持",
                    sentiment="negative",
                ),
            ]
        )

        self.assertEqual(len(result.insights), 2)
        self.assertEqual({item.review_id for item in result.insights}, {"REV-001"})

    def test_topic_result_rejects_insight_assigned_to_multiple_topics(self) -> None:
        insight = AtomicInsight(
            insight_id="INSIGHT-001",
            review_id="REV-001",
            statement="配送延迟",
            sentiment="negative",
        )
        with self.assertRaisesRegex(
            ValidationError, "Atomic Insight 只能属于一个 Topic.*INSIGHT-001"
        ):
            TopicDiscoveryResult(
                insights=[insight],
                topics=[
                    Topic(
                        topic_id="TOPIC-001",
                        name="配送时效",
                        description="订单送达过慢。",
                        insight_ids=[insight.insight_id],
                        representative_review_ids=[insight.review_id],
                    ),
                    Topic(
                        topic_id="TOPIC-002",
                        name="配送体验",
                        description="配送体验不佳。",
                        insight_ids=[insight.insight_id],
                        representative_review_ids=[insight.review_id],
                    ),
                ],
            )


if __name__ == "__main__":
    unittest.main()
