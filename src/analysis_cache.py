"""真实分析快照、运行时检查点和演示缓存的确定性存储。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.schemas import (
    FindingGenerationResult,
    ProductPlanResult,
    TestGenerationResult,
    TopicDiscoveryResult,
)


SNAPSHOT_SCHEMA_VERSION = 1


class AnalysisCacheError(RuntimeError):
    """快照无法安全读取或写入。"""


class AnalysisSnapshot(BaseModel):
    """一次真实输入及其各阶段已验证结果。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal[1] = SNAPSHOT_SCHEMA_VERSION
    snapshot_id: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    source_type: Literal[
        "app_store_us", "uploaded_file", "illustrative_sample"
    ]
    analysis_goal: str = Field(min_length=1)
    analysis_fingerprint: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    raw_reviews: list[dict[str, Any]] = Field(min_length=1)
    cleaning_report: dict[str, Any]
    collection_report: dict[str, Any] | None = None
    topic_result: TopicDiscoveryResult | None = None
    finding_result: FindingGenerationResult | None = None
    planning_result: ProductPlanResult | None = None
    test_result: TestGenerationResult | None = None

    @model_validator(mode="after")
    def downstream_results_require_upstream(self) -> "AnalysisSnapshot":
        if self.finding_result is not None and self.topic_result is None:
            raise ValueError("Finding 快照缺少上游 Topic")
        if self.planning_result is not None and self.finding_result is None:
            raise ValueError("PRD 快照缺少上游 Finding")
        if self.test_result is not None and self.planning_result is None:
            raise ValueError("测试快照缺少上游 PRD")
        if self.source_type == "app_store_us":
            if self.collection_report is None:
                raise ValueError("美国区 App Store 快照缺少采集报告")
            if self.collection_report.get("storefront") != "us":
                raise ValueError("App Store 快照必须来自美国区 storefront")
        return self

    @property
    def completed_stage(self) -> str:
        if self.test_result is not None:
            return "test"
        if self.planning_result is not None:
            return "planning"
        if self.finding_result is not None:
            return "finding"
        if self.topic_result is not None:
            return "topic"
        return "input"

    @property
    def is_complete_demo(self) -> bool:
        return (
            self.source_type == "app_store_us"
            and self.collection_report is not None
            and self.topic_result is not None
            and self.finding_result is not None
            and self.planning_result is not None
            and self.test_result is not None
            and all(
                review.get("storefront") == "us"
                and review.get("source") == "apple_public_rss_us"
                for review in self.raw_reviews
            )
        )


def create_snapshot(
    *,
    source_type: str,
    analysis_goal: str,
    analysis_fingerprint: str,
    model_name: str,
    raw_reviews: list[dict[str, Any]],
    cleaning_report: dict[str, Any],
    collection_report: dict[str, Any] | None,
    topic_result: dict[str, Any] | None,
    finding_result: dict[str, Any] | None,
    planning_result: dict[str, Any] | None,
    test_result: dict[str, Any] | None,
    now: datetime | None = None,
) -> AnalysisSnapshot:
    """从当前已验证状态创建不含密钥的版本化快照。"""
    created_at = (now or datetime.now(timezone.utc)).isoformat()
    snapshot_id = f"SNAP-{analysis_fingerprint[:12]}-{created_at[:10]}"
    return AnalysisSnapshot.model_validate(
        {
            "snapshot_id": snapshot_id,
            "created_at": created_at,
            "source_type": source_type,
            "analysis_goal": analysis_goal,
            "analysis_fingerprint": analysis_fingerprint,
            "model_name": model_name or "unknown",
            "raw_reviews": raw_reviews,
            "cleaning_report": cleaning_report,
            "collection_report": collection_report,
            "topic_result": topic_result,
            "finding_result": finding_result,
            "planning_result": planning_result,
            "test_result": test_result,
        }
    )


def save_snapshot(snapshot: AnalysisSnapshot, path: Path) -> None:
    """先写临时文件再原子替换，避免中断留下半份 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary_path.open(
            "w", encoding="utf-8", newline="\n"
        ) as file:
            file.write(snapshot.model_dump_json(indent=2))
            file.write("\n")
        temporary_path.replace(path)
    except OSError as error:
        raise AnalysisCacheError(f"分析快照写入失败：{error}") from error


def load_snapshot(path: Path) -> AnalysisSnapshot:
    """读取并验证快照结构；损坏或过期格式不会进入 UI。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return AnalysisSnapshot.model_validate(payload)
    except FileNotFoundError as error:
        raise AnalysisCacheError(f"未找到分析快照：{path.name}") from error
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise AnalysisCacheError(f"分析快照校验失败：{error}") from error


def promote_complete_demo(snapshot: AnalysisSnapshot, path: Path) -> None:
    """只有真实美国区完整闭环才能成为对外演示缓存。"""
    if not snapshot.is_complete_demo:
        raise AnalysisCacheError(
            "只有包含完整 Topic、Finding、PRD、测试结果的真实美国区运行"
            "才能保存为 Demo。"
        )
    save_snapshot(snapshot, path)
