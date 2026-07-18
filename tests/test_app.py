import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_DIR = Path(__file__).resolve().parents[1]


class StreamlitAppTests(unittest.TestCase):
    def test_default_page_runs_without_exception(self) -> None:
        app = AppTest.from_file(PROJECT_DIR / "app.py").run(timeout=15)

        self.assertEqual(len(app.exception), 0)
        self.assertIn("ReviewScope AI", app.title[0].value)
        self.assertEqual(app.metric[0].value, "6")
        self.assertEqual(app.metric[1].value, "5")
        self.assertIn("Evidence Finding", [tab.label for tab in app.tabs])
        self.assertIn("版本规划与 PRD", [tab.label for tab in app.tabs])
        self.assertIn("测试用例与追溯", [tab.label for tab in app.tabs])
        self.assertIn("美国区 App Store 实时采集", app.radio[0].options)


if __name__ == "__main__":
    unittest.main()
