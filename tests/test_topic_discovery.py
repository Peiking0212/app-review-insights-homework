import os
import unittest
from math import nan
from unittest.mock import MagicMock, patch

from src.config import ModelConfig, ModelConfigError
from src.prompts import (
    INSIGHT_EXTRACTION_SYSTEM_PROMPT,
    TOPIC_AGGREGATION_SYSTEM_PROMPT,
    build_insight_extraction_messages,
    build_topic_aggregation_messages,
)
from src.schemas import (
    AtomicInsight,
    AtomicInsightCandidate,
    InsightExtractionBatch,
    Topic,
    TopicAggregationDraft,
    TopicCandidate,
    TopicDiscoveryResult,
)
from src.topic_discovery import (
    TopicDiscoveryError,
    TopicDiscoveryService,
    apply_topic_aggregation,
    batch_reviews,
    build_model_request_options,
    materialize_insights,
    prepare_reviews,
    safe_provider_error,
    validate_insight_batch,
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

    def test_reviews_are_split_in_stable_batches(self) -> None:
        batches = batch_reviews(self.reviews, batch_size=2)

        self.assertEqual(len(batches), 2)
        self.assertEqual(
            [review.review_id for review in batches[0]],
            ["REV-0001", "REV-0002"],
        )
        self.assertEqual(
            [review.review_id for review in batches[1]], ["REV-0003"]
        )

    def test_prompts_separate_extraction_from_global_aggregation(self) -> None:
        extraction_messages = build_insight_extraction_messages(
            self.reviews[:2], "关注稳定性", 1, 2
        )
        insights = self.valid_result().insights
        aggregation_messages = build_topic_aggregation_messages(
            insights, "关注稳定性"
        )

        self.assertIn("只从本批评论提取", INSIGHT_EXTRACTION_SYSTEM_PROMPT)
        self.assertIn("不生成 Topic", INSIGHT_EXTRACTION_SYSTEM_PROMPT)
        self.assertIn("1/2", extraction_messages[1]["content"])
        self.assertIn("REV-0001", extraction_messages[1]["content"])
        self.assertIn("全量已验证", TOPIC_AGGREGATION_SYSTEM_PROMPT)
        self.assertIn("不输出 representative_review_ids", TOPIC_AGGREGATION_SYSTEM_PROMPT)
        self.assertIn("INSIGHT-001", aggregation_messages[1]["content"])

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

    def test_batch_validation_rejects_unaccounted_review(self) -> None:
        batch_result = InsightExtractionBatch(
            insights=[
                AtomicInsightCandidate(
                    review_id="REV-0001",
                    statement="登录后崩溃",
                    sentiment="negative",
                )
            ]
        )

        with self.assertRaisesRegex(TopicDiscoveryError, "本批评论未被处理"):
            validate_insight_batch(
                batch_result, {"REV-0001", "REV-0002"}
            )

    def test_python_assigns_global_insight_ids_across_batches(self) -> None:
        batch_results = [
            InsightExtractionBatch(
                insights=[
                    AtomicInsightCandidate(
                        review_id="REV-0001",
                        statement="登录后崩溃",
                        sentiment="negative",
                    )
                ]
            ),
            InsightExtractionBatch(
                insights=[
                    AtomicInsightCandidate(
                        review_id="REV-0002",
                        statement="登录反复崩溃",
                        sentiment="negative",
                    )
                ]
            ),
        ]

        insights = materialize_insights(batch_results)

        self.assertEqual(
            [insight.insight_id for insight in insights],
            ["INSIGHT-0001", "INSIGHT-0002"],
        )

    def test_python_derives_topic_ids_and_representative_reviews(self) -> None:
        insights = [
            AtomicInsight(
                insight_id="INSIGHT-0001",
                review_id="REV-0001",
                statement="登录后崩溃",
                sentiment="negative",
            ),
            AtomicInsight(
                insight_id="INSIGHT-0002",
                review_id="REV-0001",
                statement="登录后无法操作",
                sentiment="negative",
            ),
            AtomicInsight(
                insight_id="INSIGHT-0003",
                review_id="REV-0002",
                statement="登录反复崩溃",
                sentiment="negative",
            ),
        ]
        draft = TopicAggregationDraft(
            topics=[
                TopicCandidate(
                    candidate_id="TOPIC-CAND-001",
                    name="登录稳定性",
                    description="登录过程发生崩溃或不可用。",
                    insight_ids=[
                        "INSIGHT-0001",
                        "INSIGHT-0002",
                        "INSIGHT-0003",
                    ],
                )
            ]
        )

        result = apply_topic_aggregation(
            draft, insights, self.reviews, ["REV-0003"], [], 2
        )

        self.assertEqual(result.topics[0].topic_id, "TOPIC-001")
        self.assertEqual(
            result.topics[0].representative_review_ids,
            ["REV-0001", "REV-0002"],
        )
        self.assertEqual(result.extraction_batch_count, 2)

    def test_aggregation_rejects_insight_with_unknown_review(self) -> None:
        insights = [
            AtomicInsight(
                insight_id="INSIGHT-0001",
                review_id="REV-9999",
                statement="不存在的评论观点",
                sentiment="negative",
            )
        ]
        draft = TopicAggregationDraft(
            topics=[
                TopicCandidate(
                    candidate_id="TOPIC-CAND-001",
                    name="非法主题",
                    description="用于验证非法 Review 引用。",
                    insight_ids=["INSIGHT-0001"],
                )
            ]
        )

        with self.assertRaisesRegex(TopicDiscoveryError, "不存在的 Review"):
            apply_topic_aggregation(draft, insights, self.reviews, [], [], 1)

    def test_multiple_distinct_insights_from_one_review_are_allowed(self) -> None:
        result = self.valid_result()
        result.insights.append(
            AtomicInsight(
                insight_id="INSIGHT-003",
                review_id="REV-0001",
                statement="登录后无法继续操作",
                sentiment="negative",
            )
        )
        result.topics.append(
            Topic(
                topic_id="TOPIC-002",
                name="登录可用性",
                description="用户登录后无法继续使用应用。",
                insight_ids=["INSIGHT-003"],
                representative_review_ids=["REV-0001"],
            )
        )

        validate_topic_references(
            result, {review.review_id for review in self.reviews}
        )

    def test_missing_model_configuration_stops_before_api_call(self) -> None:
        with patch("src.config.load_dotenv"), patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ModelConfigError):
                ModelConfig.from_env()

    def test_deepseek_disables_thinking_for_structured_output(self) -> None:
        config = ModelConfig(
            api_key="local-test-key",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
        )

        self.assertEqual(
            build_model_request_options(config),
            {"extra_body": {"thinking": {"type": "disabled"}}},
        )

    def test_other_providers_do_not_receive_deepseek_options(self) -> None:
        config = ModelConfig(
            api_key="local-test-key",
            model="gpt-test",
            base_url="https://example.com/v1",
        )

        self.assertEqual(build_model_request_options(config), {})

    def test_service_passes_deepseek_compatibility_options(self) -> None:
        config = ModelConfig(
            api_key="local-test-key",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
        )
        structured_client = MagicMock()
        structured_client.chat.completions.create.side_effect = [
            InsightExtractionBatch(
                insights=[
                    AtomicInsightCandidate(
                        review_id="REV-0001",
                        statement="登录后应用崩溃",
                        sentiment="negative",
                    ),
                    AtomicInsightCandidate(
                        review_id="REV-0002",
                        statement="登录过程反复崩溃",
                        sentiment="negative",
                    ),
                ],
            ),
            InsightExtractionBatch(
                other_review_ids=["REV-0003"],
            ),
            TopicAggregationDraft(
                topics=[
                    TopicCandidate(
                        candidate_id="TOPIC-CAND-001",
                        name="登录稳定性",
                        description="用户登录时遇到崩溃。",
                        insight_ids=["INSIGHT-0001", "INSIGHT-0002"],
                    )
                ]
            ),
        ]

        with patch("openai.OpenAI"), patch(
            "instructor.from_openai", return_value=structured_client
        ):
            result = TopicDiscoveryService(config, batch_size=2).discover(
                self.reviews, "关注稳定性"
            )

        calls = structured_client.chat.completions.create.call_args_list
        self.assertEqual(len(calls), 3)
        for call in calls:
            self.assertEqual(
                call.kwargs["extra_body"], {"thinking": {"type": "disabled"}}
            )
        self.assertEqual(result.extraction_batch_count, 2)
        self.assertEqual(result.insights[0].insight_id, "INSIGHT-0001")
        self.assertEqual(
            result.topics[0].representative_review_ids,
            ["REV-0001", "REV-0002"],
        )

    def test_provider_error_is_unwrapped_and_secret_is_redacted(self) -> None:
        api_key = "sk-secret-value-12345678"
        root_error = ValueError(
            "Thinking mode rejected Authorization: Bearer " + api_key
        )
        wrapped_error = RuntimeError("InstructorRetryException")
        wrapped_error.__cause__ = root_error

        message = safe_provider_error(wrapped_error, api_key)

        self.assertIn("Thinking mode rejected", message)
        self.assertIn("[REDACTED]", message)
        self.assertNotIn(api_key, message)

    def test_instructor_openai_client_can_be_created(self) -> None:
        import instructor
        from openai import OpenAI

        client = instructor.from_openai(OpenAI(api_key="local-test-key"))

        self.assertIsNotNone(client.chat.completions.create)


if __name__ == "__main__":
    unittest.main()
