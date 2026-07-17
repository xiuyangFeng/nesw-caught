from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.schemas.research import (
    MarketRelevanceAnnotation,
    MarketRelevanceContent,
    MarketRelevanceLabel,
    MarketRelevanceOrigin,
    MarketRelevanceSample,
)
from app.services.news_relevance_evaluator import predict_market_relevance_details

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
    "edgar",
    "investor",
    "earnings",
    "8-k",
    "10-k",
    "10-q",
    "港交所",
    "证监会",
    "公告",
    "财报",
    "上交所",
    "深交所",
}

# 短 token 易误伤，单独用词边界匹配（如 "IR Portal"）
OFFICIAL_SOURCE_WORD_HINTS = {
    "ir",
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
    "earnings",
    "guidance",
    "8-k",
    "10-k",
    "10-q",
}

# 入库门槛：弱相关理由单独出现时不再放行（官方源除外）
WEAK_INGEST_REASONS = frozenset({"concept_mover", "sector_signal_term"})


@dataclass(frozen=True)
class NewsPriorityItem:
    title: str
    source_tier: str = "primary"
    sector_tag: str | None = None
    source_name: str = ""
    published_at: datetime | None = None
    relevance_hints: tuple[str, ...] = ()


def news_priority_key(item: NewsPriorityItem, *, now: datetime | None = None) -> tuple[object, ...]:
    current_time = _normalize_datetime(now or datetime.now(UTC))
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


def has_official_signal(source_name: str, relevance_hints: tuple[str, ...] = ()) -> bool:
    """来源名或相关性提示是否带有"官方/监管/IR/财报"信号。供排序与 editorial 评分复用。"""
    normalized_source = source_name.lower()
    if any(hint in normalized_source for hint in OFFICIAL_SOURCE_HINTS):
        return True
    # 中文源名对 lower() 无影响，显式匹配监管/交易所关键词
    if any(hint in source_name for hint in ("港交所", "证监会", "公告", "财报", "上交所", "深交所")):
        return True

    padded = f" {normalized_source} "
    if any(
        f" {word} " in padded or f"/{word} " in padded or f" {word}/" in padded
        for word in OFFICIAL_SOURCE_WORD_HINTS
    ):
        return True

    for hint in relevance_hints:
        normalized_hint = hint.lower()
        if any(official_hint in normalized_hint for official_hint in OFFICIAL_RELEVANCE_HINTS):
            return True

    return False


def passes_ingest_relevance_gate(
    *,
    title: str,
    summary: str | None = None,
    body_excerpt: str | None = None,
    source_name: str = "",
    relevance_hints: tuple[str, ...] = (),
) -> bool:
    """入库/候选阶段市场相关性门槛。

    - 官方/IR/监管/财报源优先放行
    - 其余须通过市场相关性预测，且不能仅依赖弱理由
    """
    if has_official_signal(source_name, relevance_hints):
        return True

    sample = MarketRelevanceSample(
        sample_id="ingest-gate",
        source_type="realtime",
        origin=MarketRelevanceOrigin(source_name=source_name or "unknown", canonical_url=""),
        content=MarketRelevanceContent(title=title, summary=summary, body_excerpt=body_excerpt),
        labels=MarketRelevanceLabel(market_relevant=True),
        annotation=MarketRelevanceAnnotation(label_source="model_only", confidence=0.0),
    )
    details = predict_market_relevance_details(sample)
    if not details.is_market_relevant:
        return False
    if details.relevance_reason in WEAK_INGEST_REASONS:
        return False
    return True


def _has_official_signal(item: NewsPriorityItem) -> bool:
    return has_official_signal(item.source_name, item.relevance_hints)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _recency_rank(published_at: datetime | None, now: datetime) -> float:
    if published_at is None:
        return float("inf")
    normalized_published_at = _normalize_datetime(published_at)
    return (now - normalized_published_at).total_seconds()
