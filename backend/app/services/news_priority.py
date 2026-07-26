from __future__ import annotations

import re
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

# 长且语义唯一的英文提示词：子串匹配即可（"regulator" 不会误命中别的词）。
OFFICIAL_SOURCE_HINTS = {
    "ministry",
    "regulator",
    "exchange",
    "authority",
    "department",
    "edgar",
    "investor",
    "earnings",
    "federal reserve",
    "central bank",
}

# 中文提示词：CJK 无大小写，直接对原串子串匹配。
OFFICIAL_SOURCE_CHINESE_HINTS = (
    "港交所",
    "证监会",
    "公告",
    "财报",
    "上交所",
    "深交所",
)

# 短 token 必须走词边界匹配。
#
# 修复 P0-2：此前 "sec"/"fed"/"boe" 走的是子串匹配，任何源名含 "Sector..."、
# "Federated..."、"Boeing..." 的都会被当成官方源【整源绕过相关性闸门】。
# 这里统一改为词边界匹配：前后不能紧邻 [a-z0-9]，所以
#   "SEC Press Releases" / "US-SEC" / "sec.gov"  → 命中
#   "Sector Watch" / "Federated News" / "Secondary Market Daily" → 不命中
# "8-k"/"10-k"/"10-q" 也放在这里：它们含 "-"，词边界规则对其同样成立。
OFFICIAL_SOURCE_WORD_HINTS = {
    "ir",
    "sec",
    "fed",
    "boe",
    "sfc",
    "fda",
    "ecb",
    "csrc",
    "hkex",
    "8-k",
    "10-k",
    "10-q",
}

_OFFICIAL_WORD_HINT_RE = re.compile(
    "|".join(
        rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])"
        for word in sorted(OFFICIAL_SOURCE_WORD_HINTS, key=len, reverse=True)
    )
)

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
    if any(hint in source_name for hint in OFFICIAL_SOURCE_CHINESE_HINTS):
        return True

    if _OFFICIAL_WORD_HINT_RE.search(normalized_source):
        return True

    for hint in relevance_hints:
        normalized_hint = hint.lower()
        if any(official_hint in normalized_hint for official_hint in OFFICIAL_RELEVANCE_HINTS):
            return True

    return False


@dataclass(frozen=True)
class IngestGateDecision:
    """闸门判定结果。

    修复 P0-3：此前闸门只返回 bool，被拒条目「哪条规则拒的」完全不可观测，
    运维面板上"抓了 20 入 0"无法归因、也无法调参。现在把判定理由一并返回，
    由 persister 分类计数并打进日志。
    """

    passed: bool
    reason: str


def evaluate_ingest_relevance_gate(
    *,
    title: str,
    summary: str | None = None,
    body_excerpt: str | None = None,
    source_name: str = "",
    relevance_hints: tuple[str, ...] = (),
    has_stock_refs: bool = False,
) -> IngestGateDecision:
    """入库/候选阶段市场相关性门槛（带理由）。

    - 官方/IR/监管/财报源优先放行
    - 源侧结构化的"关联个股"信号（如财联社 stock_list）高置信放行
    - 其余须通过市场相关性预测，且不能仅依赖弱理由
    """
    if has_official_signal(source_name, relevance_hints):
        return IngestGateDecision(True, "official_source")

    # WS-5b：源自己标注了关联个股，说明编辑侧已确认这条快讯挂在具体标的上。
    # 这比任何关键词表都可靠，直接放行，不必再过词表。
    if has_stock_refs:
        return IngestGateDecision(True, "structured_stock_refs")

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
        return IngestGateDecision(False, f"no_market_signal:{details.relevance_reason or 'none'}")
    if details.relevance_reason in WEAK_INGEST_REASONS:
        return IngestGateDecision(False, f"weak_signal:{details.relevance_reason}")
    return IngestGateDecision(True, f"market_signal:{details.relevance_reason}")


def passes_ingest_relevance_gate(
    *,
    title: str,
    summary: str | None = None,
    body_excerpt: str | None = None,
    source_name: str = "",
    relevance_hints: tuple[str, ...] = (),
    has_stock_refs: bool = False,
) -> bool:
    """`evaluate_ingest_relevance_gate` 的布尔薄封装（保留既有调用点签名）。"""
    return evaluate_ingest_relevance_gate(
        title=title,
        summary=summary,
        body_excerpt=body_excerpt,
        source_name=source_name,
        relevance_hints=relevance_hints,
        has_stock_refs=has_stock_refs,
    ).passed


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
