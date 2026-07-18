import unittest
from datetime import datetime, timezone
from urllib.error import URLError

from src.app_store import (
    AppStoreCollectionError,
    canonical_us_app_url,
    collect_us_reviews,
    parse_app_store_id,
)


def review_entry(
    source_id: str,
    content: str = "Useful review content.",
    rating: str = "2",
) -> dict:
    return {
        "id": {"label": source_id},
        "title": {"label": "Review title"},
        "content": {"label": content},
        "im:rating": {"label": rating},
        "im:version": {"label": "1.2.3"},
        "updated": {"label": "2026-07-18T10:00:00-07:00"},
    }


class AppStoreCollectionTests(unittest.TestCase):
    def test_parser_accepts_us_cn_and_numeric_input(self) -> None:
        self.assertEqual(
            parse_app_store_id(
                "https://apps.apple.com/us/app/workout/id839285684"
            ),
            "839285684",
        )
        self.assertEqual(
            parse_app_store_id(
                "https://apps.apple.com/cn/app/workout/id839285684?mt=8"
            ),
            "839285684",
        )
        self.assertEqual(parse_app_store_id("839285684"), "839285684")

    def test_parser_rejects_non_apple_or_missing_id(self) -> None:
        with self.assertRaises(AppStoreCollectionError):
            parse_app_store_id("https://example.com/us/app/id839285684")
        with self.assertRaises(AppStoreCollectionError):
            parse_app_store_id("https://apps.apple.com/us/app/no-id")

    def test_cn_input_still_collects_only_us_feed(self) -> None:
        requested_urls: list[str] = []

        def fetch(url: str) -> dict:
            requested_urls.append(url)
            if "lookup" in url:
                return {"resultCount": 1, "results": [{"trackName": "Demo App"}]}
            return {"feed": {"entry": [review_entry("1001")]}}

        result = collect_us_reviews(
            "https://apps.apple.com/cn/app/demo/id839285684",
            requested_review_count=1,
            fetch_json=fetch,
            sleep=lambda _: None,
        )

        self.assertEqual(result.report.storefront, "us")
        self.assertEqual(result.report.canonical_url, canonical_us_app_url("839285684"))
        self.assertEqual(result.records[0]["storefront"], "us")
        self.assertEqual(result.records[0]["source"], "apple_public_rss_us")
        self.assertTrue(all("/cn/" not in url for url in requested_urls))

    def test_empty_first_page_does_not_stop_later_page_collection(self) -> None:
        def fetch(url: str) -> dict:
            if "lookup" in url:
                return {"resultCount": 1, "results": [{"trackName": "Demo App"}]}
            if "page=1" in url:
                return {"feed": {}}
            return {"feed": {"entry": [review_entry("2001")]}}

        result = collect_us_reviews(
            "839285684",
            requested_review_count=1,
            max_pages=2,
            fetch_json=fetch,
            sleep=lambda _: None,
            now=lambda: datetime(2026, 7, 18, tzinfo=timezone.utc),
        )

        self.assertEqual(result.report.empty_pages, [1])
        self.assertEqual(result.report.pages_attempted, 2)
        self.assertEqual(result.report.collected_review_count, 1)
        self.assertIn("空页", " ".join(result.report.limitations))

    def test_duplicate_and_malformed_entries_are_reported(self) -> None:
        def fetch(url: str) -> dict:
            if "lookup" in url:
                return {"resultCount": 1, "results": [{"trackName": "Demo App"}]}
            return {
                "feed": {
                    "entry": [
                        review_entry("3001"),
                        review_entry("3001"),
                        review_entry("3002", content=""),
                    ]
                }
            }

        result = collect_us_reviews(
            "839285684",
            requested_review_count=2,
            max_pages=1,
            fetch_json=fetch,
            sleep=lambda _: None,
        )

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.report.duplicates_removed, 1)
        self.assertEqual(result.report.malformed_removed, 1)

    def test_partial_page_failure_returns_data_with_limitation(self) -> None:
        def fetch(url: str) -> dict:
            if "lookup" in url:
                return {"resultCount": 1, "results": [{"trackName": "Demo App"}]}
            if "page=1" in url:
                raise URLError("temporary failure")
            return {"feed": {"entry": [review_entry("4001")]}}

        result = collect_us_reviews(
            "839285684",
            requested_review_count=1,
            max_pages=2,
            retries=0,
            fetch_json=fetch,
            sleep=lambda _: None,
        )

        self.assertEqual(result.report.pages_succeeded, 1)
        self.assertIn("第 1 页采集失败", " ".join(result.report.limitations))

    def test_all_empty_pages_stop_and_recommend_file_fallback(self) -> None:
        def fetch(url: str) -> dict:
            if "lookup" in url:
                return {"resultCount": 1, "results": [{"trackName": "Demo App"}]}
            return {"feed": {}}

        with self.assertRaisesRegex(AppStoreCollectionError, "CSV/JSON"):
            collect_us_reviews(
                "839285684",
                requested_review_count=10,
                max_pages=2,
                fetch_json=fetch,
                sleep=lambda _: None,
            )

    def test_missing_us_lookup_result_stops_collection(self) -> None:
        with self.assertRaisesRegex(AppStoreCollectionError, "美国区"):
            collect_us_reviews(
                "839285684",
                fetch_json=lambda _: {"resultCount": 0, "results": []},
                sleep=lambda _: None,
            )


if __name__ == "__main__":
    unittest.main()
