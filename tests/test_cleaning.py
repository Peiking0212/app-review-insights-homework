import json
import unittest
from pathlib import Path

from src.cleaning import clean_review_records


PROJECT_DIR = Path(__file__).resolve().parents[1]


class ReviewCleaningTests(unittest.TestCase):
    def test_sample_data_reports_duplicate_id(self) -> None:
        with (PROJECT_DIR / "data" / "sample_reviews.json").open(
            "r", encoding="utf-8"
        ) as file:
            reviews = json.load(file)

        cleaned, report = clean_review_records(reviews)

        self.assertEqual(len(cleaned), 5)
        self.assertEqual(report.raw_count, 6)
        self.assertEqual(report.duplicate_review_id, 1)
        self.assertEqual(report.removed_count, 1)
        self.assertAlmostEqual(report.retention_rate, 5 / 6)

    def test_each_invalid_record_is_counted_once(self) -> None:
        reviews = [
            {"review_id": "", "rating": 5, "content": "missing id"},
            {"review_id": "REV-1", "rating": 9, "content": "bad rating"},
            {"review_id": "REV-2", "rating": 3, "content": "   "},
            {"review_id": "REV-3", "rating": "4", "content": "Useful"},
            {"review_id": "REV-3", "rating": 4, "content": "duplicate id"},
            {"review_id": "REV-4", "rating": 4, "content": " useful  "},
        ]

        cleaned, report = clean_review_records(reviews)

        self.assertEqual([review["review_id"] for review in cleaned], ["REV-3"])
        self.assertEqual(report.invalid_review_id, 1)
        self.assertEqual(report.invalid_rating, 1)
        self.assertEqual(report.empty_content, 1)
        self.assertEqual(report.duplicate_review_id, 1)
        self.assertEqual(report.duplicate_content, 1)
        self.assertEqual(report.removed_count, 5)

    def test_fractional_and_boolean_ratings_are_invalid(self) -> None:
        reviews = [
            {"review_id": "REV-1", "rating": 2.5, "content": "fraction"},
            {"review_id": "REV-2", "rating": True, "content": "boolean"},
            {"review_id": "REV-3", "rating": "5.0", "content": "valid"},
        ]

        cleaned, report = clean_review_records(reviews)

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["rating"], 5)
        self.assertEqual(report.invalid_rating, 2)


if __name__ == "__main__":
    unittest.main()
