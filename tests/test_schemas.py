import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.schemas import Finding, Requirement, Review, TestCase, Topic


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
                representative_review_ids=["FIND-001"],
            )


if __name__ == "__main__":
    unittest.main()
