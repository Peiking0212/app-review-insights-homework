"""美国区 App Store 公开评论采集与透明失败报告。"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


US_STOREFRONT = "us"
MAX_FEED_PAGES = 10
REVIEWS_PER_PAGE = 50
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_RETRIES = 1
DEFAULT_REQUEST_INTERVAL_SECONDS = 0.2


class AppStoreCollectionError(RuntimeError):
    """无法安全获得可用的美国区评论。"""


@dataclass(frozen=True)
class CollectionReport:
    """采集过程的可审计信息，不包含模型推断。"""

    app_id: str
    app_name: str
    storefront: str
    canonical_url: str
    collected_at: str
    requested_review_count: int
    collected_review_count: int
    pages_attempted: int
    pages_succeeded: int
    empty_pages: list[int] = field(default_factory=list)
    duplicates_removed: int = 0
    malformed_removed: int = 0
    source_urls: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CollectionResult:
    records: list[dict[str, Any]]
    report: CollectionReport


def parse_app_store_id(value: str) -> str:
    """从 App Store 链接或纯数字输入提取 App ID，并拒绝其他站点。"""
    normalized = value.strip()
    if re.fullmatch(r"\d{6,}", normalized):
        return normalized
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "apps.apple.com":
        raise AppStoreCollectionError(
            "请输入 apps.apple.com 的 App Store 链接或纯数字 App ID。"
        )
    match = re.search(r"(?:^|/)id(\d+)(?:/|$)", parsed.path)
    if match is None:
        raise AppStoreCollectionError("链接中没有找到形如 id839285684 的 App ID。")
    return match.group(1)


def canonical_us_app_url(app_id: str) -> str:
    return f"https://apps.apple.com/us/app/id{app_id}"


def review_feed_url(app_id: str, page: int) -> str:
    return (
        "https://itunes.apple.com/us/rss/customerreviews/"
        f"page={page}/id={app_id}/sortby=mostrecent/json"
    )


def lookup_url(app_id: str) -> str:
    return f"https://itunes.apple.com/lookup?id={app_id}&country=us"


def _fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ReviewScopeAI-Homework/1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _label(container: dict[str, Any], key: str) -> str:
    value = container.get(key, {})
    if isinstance(value, dict):
        return str(value.get("label") or "").strip()
    return ""


def _entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("feed", {}).get("entry", [])
    if isinstance(entries, dict):
        return [entries]
    if isinstance(entries, list):
        return [entry for entry in entries if isinstance(entry, dict)]
    return []


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    source_id = _label(entry, "id")
    content = _label(entry, "content")
    rating = _label(entry, "im:rating")
    if not source_id or not content or not rating.isdigit():
        return None
    numeric_rating = int(rating)
    if numeric_rating < 1 or numeric_rating > 5:
        return None
    published_at = _label(entry, "updated")[:10] or None
    safe_source_id = re.sub(r"[^A-Za-z0-9_-]", "-", source_id)
    return {
        "review_id": f"REV-AS-{safe_source_id}",
        "source_id": source_id,
        "title": _label(entry, "title"),
        "content": content,
        "rating": numeric_rating,
        "version": _label(entry, "im:version") or None,
        "published_at": published_at,
        "storefront": US_STOREFRONT,
        "source": "apple_public_rss_us",
    }


def _call_with_retry(
    fetch_json: Callable[[str], dict[str, Any]],
    url: str,
    retries: int,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for _ in range(retries + 1):
        try:
            return fetch_json(url)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            last_error = error
    if last_error is None:
        raise AppStoreCollectionError("采集请求失败，但没有返回可诊断原因。")
    raise last_error


def _safe_error(error: Exception) -> str:
    if isinstance(error, HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, URLError):
        return f"网络错误：{error.reason}"
    return f"{type(error).__name__}: {' '.join(str(error).split())[:180]}"


def collect_us_reviews(
    app_url_or_id: str,
    requested_review_count: int = 100,
    *,
    max_pages: int = MAX_FEED_PAGES,
    retries: int = DEFAULT_RETRIES,
    request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] | None = None,
) -> CollectionResult:
    """有限分页采集美国区公开评论；部分失败可返回，完全失败则明确停止。"""
    if requested_review_count < 1 or requested_review_count > 500:
        raise AppStoreCollectionError("评论数量必须在 1～500 之间。")
    if max_pages < 1 or max_pages > MAX_FEED_PAGES:
        raise AppStoreCollectionError(f"采集页数必须在 1～{MAX_FEED_PAGES} 之间。")
    app_id = parse_app_store_id(app_url_or_id)
    fetch = fetch_json or _fetch_json

    try:
        lookup_payload = _call_with_retry(fetch, lookup_url(app_id), retries)
    except Exception as error:
        raise AppStoreCollectionError(
            "无法验证该 App 在美国区是否可用。"
            f"原因：{_safe_error(error)}。请改用 CSV/JSON 导入。"
        ) from error
    lookup_results = lookup_payload.get("results", [])
    if not lookup_results:
        raise AppStoreCollectionError(
            "该 App ID 在美国区 Lookup API 中没有结果，请确认链接或改用文件导入。"
        )
    app_name = str(lookup_results[0].get("trackName") or f"App {app_id}")

    records: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    source_urls: list[str] = []
    empty_pages: list[int] = []
    limitations: list[str] = []
    pages_succeeded = 0
    duplicates_removed = 0
    malformed_removed = 0

    for page in range(1, max_pages + 1):
        url = review_feed_url(app_id, page)
        source_urls.append(url)
        try:
            payload = _call_with_retry(fetch, url, retries)
        except Exception as error:
            limitations.append(f"第 {page} 页采集失败：{_safe_error(error)}")
            continue
        pages_succeeded += 1
        page_entries = _entries(payload)
        if not page_entries:
            empty_pages.append(page)
        for entry in page_entries:
            record = _normalize_entry(entry)
            if record is None:
                malformed_removed += 1
                continue
            if record["source_id"] in seen_source_ids:
                duplicates_removed += 1
                continue
            seen_source_ids.add(record["source_id"])
            records.append(record)
            if len(records) >= requested_review_count:
                break
        if len(records) >= requested_review_count:
            break
        if request_interval_seconds > 0 and page < max_pages:
            sleep(request_interval_seconds)

    if not records:
        detail = "；".join(limitations) if limitations else "公开 Feed 返回空数据"
        raise AppStoreCollectionError(
            "未获得可用的美国区书面评论。"
            f"{detail}。这不代表 App 没有评论，请改用 CSV/JSON 或稍后重试。"
        )
    if empty_pages:
        limitations.append(
            "公开 RSS Feed 存在空页且页码可能不连续，本次仍扫描了有限页数。"
        )
    if len(records) < requested_review_count:
        limitations.append(
            f"请求 {requested_review_count} 条，实际仅获得 {len(records)} 条可用评论。"
        )
    timestamp = (now or (lambda: datetime.now(timezone.utc)))().astimezone(
        timezone.utc
    )
    return CollectionResult(
        records=records,
        report=CollectionReport(
            app_id=app_id,
            app_name=app_name,
            storefront=US_STOREFRONT,
            canonical_url=canonical_us_app_url(app_id),
            collected_at=timestamp.isoformat(),
            requested_review_count=requested_review_count,
            collected_review_count=len(records),
            pages_attempted=len(source_urls),
            pages_succeeded=pages_succeeded,
            empty_pages=empty_pages,
            duplicates_removed=duplicates_removed,
            malformed_removed=malformed_removed,
            source_urls=source_urls,
            limitations=limitations,
        ),
    )
