from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

TIER_RANKS = {
    "primary": 3,
    "secondary": 2,
    "fallback": 1,
}

OFFICIAL_SOURCE_HINTS = {
    "sec",
    "hkex",
    "csrc",
    "sfc",
    "fda",
    "fed",
    "ecb",
    "boe",
    "ministry",
    "regulator",
    "exchange",
    "authority",
    "department",
}

OFFICIAL_RELEVANCE_HINTS = {
    "filing",
    "regulatory",
    "regulation",
    "disclosure",
    "announcement",
    "notice",
    "prospectus",
    "consultation",
    "approval",
    "circular",
}


@dataclass(frozen=True)
class NewsPriorityItem:
    title: str
    source_tier: str = "primary"
    sector_tag: str | None = None
    source_name: str = ""
    published_at: datetime | None = None
    relevance_hints: tuple[str, ...] = ()


def news_priority_key(item: NewsPriorityItem, *, now: datetime | None = None) -> tuple[object, ...]:
    current_time = _normalize_datetime(now or datetime.now(timezone.utc))
    tier_rank = TIER_RANKS.get(item.source_tier, 0)
    sector_rank = 1 if item.sector_tag else 0
    official_rank = 1 if _has_official_signal(item) else 0
    recency_rank = _recency_rank(item.published_at, current_time)
    return (
        -tier_rank,
        -sector_rank,
        -official_rank,
        recency_rank,
        item.title.lower(),
        item.source_name.lower(),
    )


def rank_news_items(items: list[NewsPriorityItem], *, now: datetime | None = None) -> list[NewsPriorityItem]:
    return sorted(items, key=lambda item: news_priority_key(item, now=now))


def _has_official_signal(item: NewsPriorityItem) -> bool:
    source_name = item.source_name.lower()
    if any(hint in source_name for hint in OFFICIAL_SOURCE_HINTS):
        return True

    for hint in item.relevance_hints:
        normalized_hint = hint.lower()
        if any(official_hint in normalized_hint for official_hint in OFFICIAL_RELEVANCE_HINTS):
            return True

    return False


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _recency_rank(published_at: datetime | None, now: datetime) -> float:
    if published_at is None:
        return float("inf")
    normalized_published_at = _normalize_datetime(published_at)
    return (now - normalized_published_at).total_seconds()
