"""不依赖大模型的评论清洗与审计报告。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class CleaningReport:
    """记录每条清洗规则移除的评论数量。"""

    raw_count: int
    invalid_review_id: int
    invalid_rating: int
    empty_content: int
    duplicate_review_id: int
    duplicate_content: int
    cleaned_count: int

    @property
    def removed_count(self) -> int:
        return self.raw_count - self.cleaned_count

    @property
    def retention_rate(self) -> float:
        if self.raw_count == 0:
            return 0.0
        return self.cleaned_count / self.raw_count

    def as_table_rows(self) -> list[dict[str, Any]]:
        """返回适合在 UI 中展示的逐步清洗说明。"""
        return [
            {
                "步骤": "1. 评论 ID 检查",
                "移除数量": self.invalid_review_id,
                "规则说明": "删除 review_id 为空的记录，保证后续证据可以追溯。",
            },
            {
                "步骤": "2. 评分合法性检查",
                "移除数量": self.invalid_rating,
                "规则说明": "评分必须是 1 到 5 的整数，无法解析或超出范围时删除。",
            },
            {
                "步骤": "3. 评论正文检查",
                "移除数量": self.empty_content,
                "规则说明": "删除正文为空或只包含空白字符的记录。",
            },
            {
                "步骤": "4. 评论 ID 去重",
                "移除数量": self.duplicate_review_id,
                "规则说明": "相同 review_id 只保留第一次出现的记录。",
            },
            {
                "步骤": "5. 评论正文去重",
                "移除数量": self.duplicate_content,
                "规则说明": "忽略大小写和多余空白后，正文相同的评论只保留一条。",
            },
        ]


def _parse_rating(value: Any) -> int | None:
    """将 1～5 的整数评分转换为 int，非法评分返回 None。"""
    if isinstance(value, bool) or value is None:
        return None
    try:
        rating = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if rating != rating.to_integral_value() or not 1 <= rating <= 5:
        return None
    return int(rating)


def clean_review_records(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], CleaningReport]:
    """按固定顺序清洗评论，并返回清洗后的数据与审计报告。"""
    source_records = [dict(record) for record in records]
    cleaned: list[dict[str, Any]] = []
    seen_review_ids: set[str] = set()
    seen_contents: set[str] = set()

    counts = {
        "invalid_review_id": 0,
        "invalid_rating": 0,
        "empty_content": 0,
        "duplicate_review_id": 0,
        "duplicate_content": 0,
    }

    for record in source_records:
        review_id = str(record.get("review_id") or "").strip()
        if not review_id:
            counts["invalid_review_id"] += 1
            continue

        rating = _parse_rating(record.get("rating"))
        if rating is None:
            counts["invalid_rating"] += 1
            continue

        content = " ".join(str(record.get("content") or "").split())
        if not content:
            counts["empty_content"] += 1
            continue

        if review_id in seen_review_ids:
            counts["duplicate_review_id"] += 1
            continue

        content_key = content.casefold()
        if content_key in seen_contents:
            counts["duplicate_content"] += 1
            continue

        normalized = record.copy()
        normalized["review_id"] = review_id
        normalized["rating"] = rating
        normalized["content"] = content
        cleaned.append(normalized)
        seen_review_ids.add(review_id)
        seen_contents.add(content_key)

    report = CleaningReport(
        raw_count=len(source_records),
        cleaned_count=len(cleaned),
        **counts,
    )
    return cleaned, report
