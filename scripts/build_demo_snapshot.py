"""用真实美国区评论运行完整闭环并生成可审计 Demo 快照。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.analysis_cache import create_snapshot, promote_complete_demo  # noqa: E402
from src.app_store import collect_us_reviews  # noqa: E402
from src.cleaning import clean_review_records  # noqa: E402
from src.config import ModelConfig  # noqa: E402
from src.finding_analysis import FindingAnalysisService  # noqa: E402
from src.product_planning import ProductPlanningService  # noqa: E402
from src.test_generation import TestGenerationService  # noqa: E402
from src.topic_discovery import TopicDiscoveryService, prepare_reviews  # noqa: E402


DEFAULT_APP_URL = (
    "https://apps.apple.com/us/app/"
    "workout-for-women-home-gym/id839285684"
)
DEFAULT_GOAL = "了解用户最主要的不满，并找出优先改进方向"


def analysis_fingerprint(records: list[dict], goal: str) -> str:
    serialized = json.dumps(
        {"reviews": records, "goal": goal},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-url", default=DEFAULT_APP_URL)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--goal", default=DEFAULT_GOAL)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "data" / "demo_snapshot.json",
    )
    args = parser.parse_args()

    config = ModelConfig.from_env()
    print(f"[1/6] 采集 {args.count} 条美国区公开评论")
    collection = collect_us_reviews(
        args.app_url, requested_review_count=args.count
    )
    cleaned_records, cleaning_report = clean_review_records(collection.records)
    reviews = prepare_reviews(cleaned_records)
    prepared_records = [review.model_dump(mode="json") for review in reviews]
    fingerprint = analysis_fingerprint(prepared_records, args.goal)

    print(f"[2/6] 动态主题：{len(reviews)} 条有效评论")
    topic_result = TopicDiscoveryService(config).discover(reviews, args.goal)
    print(f"[3/6] Evidence Finding：{len(topic_result.topics)} 个 Topic")
    finding_result = FindingAnalysisService(config).generate(
        reviews, topic_result, args.goal
    )
    print(f"[4/6] 版本规划与 PRD：{len(finding_result.findings)} 个 Finding")
    planning_result = ProductPlanningService(config).generate(
        reviews, topic_result, finding_result, args.goal
    )
    print(f"[5/6] 测试与完整追溯：{len(planning_result.requirements)} 条需求")
    test_result = TestGenerationService(config).generate(
        reviews, finding_result, planning_result, args.goal
    )

    snapshot = create_snapshot(
        source_type="app_store_us",
        analysis_goal=args.goal,
        analysis_fingerprint=fingerprint,
        model_name=config.model,
        raw_reviews=collection.records,
        cleaning_report=asdict(cleaning_report),
        collection_report=asdict(collection.report),
        topic_result=topic_result.model_dump(mode="json"),
        finding_result=finding_result.model_dump(mode="json"),
        planning_result=planning_result.model_dump(mode="json"),
        test_result=test_result.model_dump(mode="json"),
    )
    promote_complete_demo(snapshot, args.output)
    print(
        f"[6/6] 已生成真实 Demo：{args.output}\n"
        f"评论 {len(reviews)}｜Topic {len(topic_result.topics)}｜"
        f"Finding {len(finding_result.findings)}｜"
        f"Requirement {len(planning_result.requirements)}｜"
        f"TestCase {len(test_result.test_cases)}"
    )


if __name__ == "__main__":
    main()
