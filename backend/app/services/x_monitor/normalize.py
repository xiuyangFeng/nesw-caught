from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from hashlib import sha256

from app.schemas.x_monitor import XPostSummaryView

from .constants import VALID_MARKETS, VALID_TIERS
from .errors import XMonitorDisabledError


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return _normalize_datetime(datetime.fromisoformat(normalized))
    except ValueError:
        try:
            return _normalize_datetime(parsedate_to_datetime(value.strip()))
        except (TypeError, ValueError, IndexError):
            return None


def _extract_post_id(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else None


def _normalize_content(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def _posted_hour_bucket(posted_at: datetime | None) -> str:
    if posted_at is None:
        return "unknown"
    normalized = _normalize_datetime(posted_at)
    return normalized.strftime("%Y-%m-%dT%H")


def _dedupe_hash(handle: str, content_text: str, posted_at: datetime | None) -> str:
    material = f"{handle.lower()}|{_normalize_content(content_text)}|{_posted_hour_bucket(posted_at)}"
    return sha256(material.encode("utf-8")).hexdigest()


def _extract_symbols(raw_tweet: dict[str, object]) -> list[str]:
    raw_symbols = raw_tweet.get("symbols")
    if isinstance(raw_symbols, list):
        return [str(item).upper().strip() for item in raw_symbols if str(item).strip()]

    content_text = str(raw_tweet.get("text") or "")
    cashtags = re.findall(r"\$([A-Za-z][A-Za-z0-9._-]{0,9})", content_text)
    seen: list[str] = []
    for symbol in cashtags:
        normalized = symbol.upper().strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
    return seen


def _infer_market(symbols: list[str], default_market: str | None = None) -> str:
    if default_market in VALID_MARKETS:
        return str(default_market)
    for symbol in symbols:
        if symbol.endswith(".HK") or symbol.startswith("HK"):
            return "hk"
    return "us"


def _extract_author_handle(raw_tweet: dict[str, object]) -> str:
    author = raw_tweet.get("author")
    if isinstance(author, dict):
        handle = str(author.get("userName") or author.get("screen_name") or "").lstrip("@").strip()
        if handle:
            return handle
    return str(raw_tweet.get("userName") or "").lstrip("@").strip()


def _extract_author_name(raw_tweet: dict[str, object], fallback_handle: str) -> str:
    author = raw_tweet.get("author")
    if isinstance(author, dict):
        name = str(author.get("name") or "").strip()
        if name:
            return name
    return fallback_handle


def _normalize_handle(value: str) -> str:
    return value.lstrip("@").strip()


def _ensure_enabled(settings) -> None:
    if not settings.x_monitor_enabled:
        raise XMonitorDisabledError("x monitor is disabled")


def _normalize_account_row(item: object) -> dict[str, object] | None:
    """Normalize one raw accounts-file entry into a repository payload.

    Returns None when the entry is not a dict or has no usable handle.
    Unknown tiers fall back to "watch".
    """
    if not isinstance(item, dict):
        return None
    handle = _normalize_handle(str(item.get("handle") or ""))
    if not handle:
        return None
    tier = str(item.get("tier") or "watch").strip().lower()
    if tier not in VALID_TIERS:
        tier = "watch"
    return {
        "handle": handle,
        "display_name": str(item.get("display_name") or handle),
        "market_focus": str(item.get("market_focus")) if item.get("market_focus") else None,
        "is_active": bool(item.get("is_active", True)),
        "priority": int(item.get("priority", 0)),
        "tier": tier,
        "source": "file_import",
        "notes": str(item.get("notes")) if item.get("notes") else None,
    }


def _tweet_summary_view(
    raw_tweet: dict[str, object],
    *,
    fallback_handle: str | None = None,
    fallback_name: str | None = None,
    fallback_market: str | None = None,
) -> XPostSummaryView | None:
    """Normalize one raw provider tweet into a summary view (None when unusable)."""
    account_handle = _extract_author_handle(raw_tweet) or str(fallback_handle or "").strip()
    content_text = str(raw_tweet.get("text") or raw_tweet.get("fullText") or "").strip()
    if not account_handle or not content_text:
        return None

    symbols = _extract_symbols(raw_tweet)
    posted_at = _parse_datetime(str(raw_tweet.get("createdAt") or raw_tweet.get("created_at") or ""))
    canonical_url = str(raw_tweet.get("url") or "").strip() or None
    market = _infer_market(symbols, fallback_market)

    return XPostSummaryView(
        id=0,
        account_handle=account_handle,
        account_display_name=_extract_author_name(raw_tweet, fallback_name or account_handle),
        content_text=content_text,
        canonical_url=canonical_url,
        market=market,
        sentiment_label="unknown",
        relevance_score=None,
        posted_at=posted_at,
        captured_at=_utc_now(),
        symbols=symbols,
    )
