"""规则实体识别：用 A 股内存索引把新闻映射到 news_stock_mention。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_stock_mention import NewsStockMention
from app.services.a_share_search_service import get_all_a_shares

# 双字及歧义简称：只允许标题/正文出现全称或代码时才关联。
MENTION_STOP_NAMES = frozenset({"国安", "华夏", "东方", "中国", "科技", "控股", "集团", "股份"})


@dataclass(frozen=True)
class MentionHit:
    symbol: str
    market: str
    display_name: str
    confidence: float
    where: str


@dataclass
class MentionIndex:
    names: list[tuple[str, str, str]]  # name, symbol, market 按名称长度降序
    codes: dict[str, tuple[str, str]]  # 6 位代码 -> symbol, market


def build_mention_index(stocks: list[dict[str, str]] | None = None) -> MentionIndex:
    rows = stocks if stocks is not None else get_all_a_shares()
    names: list[tuple[str, str, str]] = []
    codes: dict[str, tuple[str, str]] = {}
    for stock in rows:
        symbol = stock["symbol"].upper()
        market = stock.get("market") or "cn"
        name = (stock.get("display_name") or "").strip()
        digits = symbol.split(".", 1)[0]
        if digits.isdigit() and len(digits) == 6:
            codes[digits] = (symbol, market)
        if len(name) >= 3 and name not in MENTION_STOP_NAMES:
            names.append((name, symbol, market))
    names.sort(key=lambda item: len(item[0]), reverse=True)
    return MentionIndex(names=names, codes=codes)


_INDEX: MentionIndex | None = None


def get_mention_index() -> MentionIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = build_mention_index()
    return _INDEX


def match_a_share_mentions(
    title: str,
    summary: str | None = None,
    body: str | None = None,
    *,
    index: MentionIndex | None = None,
) -> list[MentionHit]:
    idx = index if index is not None else get_mention_index()
    title_text = title or ""
    summary_text = summary or ""
    body_text = body or ""
    hits: dict[str, MentionHit] = {}

    def _record(symbol: str, market: str, display_name: str, where: str, confidence: float) -> None:
        current = hits.get(symbol)
        if current is None or confidence > current.confidence:
            hits[symbol] = MentionHit(
                symbol=symbol,
                market=market,
                display_name=display_name,
                confidence=confidence,
                where=where,
            )

    for name, symbol, market in idx.names:
        if name in title_text:
            _record(symbol, market, name, "title", 0.9)
        elif name in summary_text:
            _record(symbol, market, name, "summary", 0.7)
        elif name in body_text:
            _record(symbol, market, name, "body", 0.55)

    for digits, (symbol, market) in idx.codes.items():
        if digits in title_text:
            _record(symbol, market, digits, "title", 0.95)
        elif digits in summary_text:
            _record(symbol, market, digits, "summary", 0.75)
        elif digits in body_text:
            _record(symbol, market, digits, "body", 0.6)

    return sorted(hits.values(), key=lambda hit: (-hit.confidence, hit.symbol))


def persist_rule_mentions(session: Session, news_id: int, hits: list[MentionHit]) -> int:
    written = 0
    for hit in hits:
        existing = session.scalar(
            select(NewsStockMention).where(
                NewsStockMention.news_id == news_id,
                NewsStockMention.symbol == hit.symbol,
            )
        )
        if existing is not None:
            if existing.mention_type == "rule" and hit.confidence > existing.confidence:
                existing.confidence = hit.confidence
            continue
        session.add(
            NewsStockMention(
                news_id=news_id,
                symbol=hit.symbol,
                market=hit.market,
                mention_type="rule",
                confidence=hit.confidence,
            )
        )
        written += 1
    return written
