import json
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SAMPLE_FILE = PROJECT_DIR / "data" / "sample_reviews.json"
REQUIRED_FIELDS = {"review_id", "rating", "content"}


class SampleReviewDataTests(unittest.TestCase):
    def setUp(self) -> None:
        with SAMPLE_FILE.open("r", encoding="utf-8") as file:
            self.reviews = json.load(file)

    def test_sample_file_contains_reviews(self) -> None:
        self.assertGreater(len(self.reviews), 0)

    def test_each_review_has_required_fields(self) -> None:
        for review in self.reviews:
            self.assertTrue(REQUIRED_FIELDS.issubset(review))

    def test_sample_contains_one_duplicate_for_cleaning_demo(self) -> None:
        review_ids = [review["review_id"] for review in self.reviews]
        self.assertEqual(len(review_ids), 6)
        self.assertEqual(len(set(review_ids)), 5)


if __name__ == "__main__":
    unittest.main()
