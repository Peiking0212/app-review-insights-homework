import os
import unittest
from math import nan
from unittest.mock import patch

from src.config import ModelConfig, ModelConfigError
from src.prompts import TOPIC_SYSTEM_PROMPT, build_topic_messages
from src.schemas import AtomicInsight, Topic, TopicDiscoveryResult
from src.topic_discovery import (
    TopicDiscoveryError,
    prepare_reviews,
    validate_topic_references,
)


class TopicDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reviews = prepare_reviews(
            [
                {
                    "review_id": "apple-101",
                    "rating": 1,
                    "content": "The app crashes after login.",
                },
                {
                    "review_id": "apple-102",
                    "rating": 2,
                    "content": "Login crashes every time.",
                },
                {
                    "review_id": "apple-103",
                    "rating": 5,
                    "content": "This review only says hello.",
                },
            ]
        )

    def valid_result(self) -> TopicDiscoveryResult:
        return TopicDiscoveryResult(
            insights=[
                AtomicInsight(
                    insight_id="INSIGHT-001",
                    review_id="REV-0001",
                    statement="登录后应用崩溃",
                    sentiment="negative",
                ),
                AtomicInsight(
                    insight_id="INSIGHT-002",
                    review_id="REV-0002",
                    statement="登录过程反复崩溃",
                    sentiment="negative",
                ),
            ],
            topics=[
                Topic(
                    topic_id="TOPIC-001",
                    name="登录稳定性",
                    description="用户在登录时遇到崩溃。",
                    insight_ids=["INSIGHT-001", "INSIGHT-002"],
                    representative_review_ids=["REV-0001", "REV-0002"],
                )
            ],
            other_review_ids=["REV-0003"],
        )

    def test_prepare_reviews_assigns_internal_ids_and_preserves_source_ids(self) -> None:
        self.assertEqual(self.reviews[0].review_id, "REV-0001")
        self.assertEqual(self.reviews[0].source_id, "apple-101")
        self.assertEqual(self.reviews[0].source, "uploaded_file")

    def test_prepare_reviews_accepts_csv_missing_values(self) -> None:
        reviews = prepare_reviews(
            [
                {
                    "review_id": "csv-1",
                    "rating": 4,
                    "content": "Useful app.",
                    "title": nan,
                    "version": nan,
                    "published_at": nan,
                }
            ]
        )

        self.assertEqual(reviews[0].title, "")
        self.assertIsNone(reviews[0].version)
        self.assertIsNone(reviews[0].published_at)

    def test_prompt_contains_current_reviews_without_fixed_taxonomy(self) -> None:
        messages = build_topic_messages(self.reviews, "关注稳定性")

        self.assertIn("禁止使用预设行业分类", TOPIC_SYSTEM_PROMPT)
        self.assertIn("REV-0001", messages[1]["content"])
        self.assertIn("关注稳定性", messages[1]["content"])

    def test_valid_result_passes_deterministic_reference_check(self) -> None:
        validate_topic_references(
            self.valid_result(), {review.review_id for review in self.reviews}
        )

    def test_hallucinated_review_id_is_rejected(self) -> None:
        result = self.valid_result()
        result.insights[0].review_id = "REV-9999"

        with self.assertRaisesRegex(TopicDiscoveryError, "不存在的评论"):
            validate_topic_references(
                result, {review.review_id for review in self.reviews}
            )

    def test_unaccounted_review_is_rejected(self) -> None:
        result = self.valid_result()
        result.other_review_ids = []

        with self.assertRaisesRegex(TopicDiscoveryError, "既未提取"):
            validate_topic_references(
                result, {review.review_id for review in self.reviews}
            )

    def test_missing_model_configuration_stops_before_api_call(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ModelConfigError):
                ModelConfig.from_env()

    def test_instructor_openai_client_can_be_created(self) -> None:
        import instructor
        from openai import OpenAI

        client = instructor.from_openai(OpenAI(api_key="local-test-key"))

        self.assertIsNotNone(client.chat.completions.create)


if __name__ == "__main__":
    unittest.main()
