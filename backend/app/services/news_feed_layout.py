from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

from app.models.watchlist_item import WatchlistItem
from app.repositories.news_repository import NewsRepository
from app.repositories.topic_repository import TopicRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.news import (
    NewsEventDetailView,
    NewsFeedEventCardView,
    NewsFeedLayoutView,
    NewsFeedTopicView,
    NewsItemSummary,
)
from app.schemas.topic import TopicItemView
from app.services.news_priority import has_official_signal

EVENT_TYPE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "earnings",
        (
            "earnings",
            "revenue",
            "guidance",
            "results",
            "profit",
            "财报",
            "营收",
            "业绩",
            "盈利",
            "季度",
            "年报",
            "季报",
        ),
    ),
    (
        "macro",
        (
            "inflation",
            "rate",
            "fed",
            "ecb",
            "cpi",
            "gdp",
            "jobs",
            "宏观",
            "通胀",
            "CPI",
            "GDP",
            "降息",
            "加息",
            "利率",
            "就业",
            "非农",
        ),
    ),
    (
        "regulation",
        (
            "sec",
            "regulator",
            "antitrust",
            "tariff",
            "approval",
            "filing",
            "policy",
            "监管",
            "反垄断",
            "关税",
            "审批",
            "备案",
            "政策",
            "处罚",
            "制裁",
            "合规",
        ),
    ),
    (
        "product",
        (
            "launch",
            "release",
            "model",
            "chip",
            "product",
            "platform",
            "发布",
            "新品",
            "上线",
            "芯片",
            "产品",
            "型号",
            "旗舰",
        ),
    ),
    (
        "mna",
        (
            "acquire",
            "merger",
            "deal",
            "acquisition",
            "stake",
            "buyout",
            "收购",
            "并购",
            "合并",
            "入股",
            "注资",
            "重组",
            "要约",
        ),
    ),
    (
        "supply_chain",
        (
            "supplier",
            "demand",
            "shipment",
            "shipments",
            "order",
            "orders",
            "capacity",
            "factory",
            "供应链",
            "产能",
            "出货",
            "订单",
            "需求",
            "交付",
            "工厂",
            "扩产",
        ),
    ),
    (
        "market_move",
        (
            "rally",
            "selloff",
            "surge",
            "slump",
            "jump",
            "drop",
            "大涨",
            "大跌",
            "暴涨",
            "暴跌",
            "飙升",
            "跳水",
            "异动",
            "拉升",
            "杀跌",
        ),
    ),
)

SOURCE_TIER_WEIGHTS: dict[str, float] = {
    "primary": 1.2,
    "secondary": 1.0,
    "fallback": 0.7,
}

DEFAULT_SOURCE_WEIGHT = 1.0

DECAY_LAMBDA = 0.03

# editorial 评分权重(集中声明,便于调参与灰度)
EDITORIAL_TOPIC_WEIGHT = 0.4
EDITORIAL_SOURCE_WEIGHT = 0.25
EDITORIAL_FRESHNESS_WEIGHT = 0.2
EDITORIAL_MENTION_BONUS = 0.15
EDITORIAL_OFFICIAL_BONUS = 0.1


def _source_weight_map() -> dict[str, float]:
    from app.services.news_ingestion import load_sources

    return {
        source.name: SOURCE_TIER_WEIGHTS.get(source.tier, DEFAULT_SOURCE_WEIGHT)
        for source in load_sources()
    }


def _decayed_importance(score: float, last_seen_at: datetime | None) -> float:
    if last_seen_at is None:
        return score
    now = datetime.now(timezone.utc)
    ts = last_seen_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    hours = max(0, (now - ts).total_seconds()) / 3600
    return round(score * math.exp(-DECAY_LAMBDA * hours), 4)


def _event_type_from_texts(texts: Iterable[str]) -> str:
    haystack = " ".join(texts).lower()
    for event_type, patterns in EVENT_TYPE_PATTERNS:
        if any(pattern in haystack for pattern in patterns):
            return event_type
    return "general"


def _timestamp_value(value: datetime | None) -> float:
    if value is None:
        return float("-inf")
    return value.timestamp()


def _news_sort_key(item: NewsItemSummary) -> tuple[float, float, int]:
    return (
        _timestamp_value(item.published_at),
        _timestamp_value(item.fetched_at),
        item.id,
    )


def _qualifies_as_event(topic: TopicItemView) -> bool:
    return topic.importance_score >= 0.55 or topic.news_count >= 2 or bool(topic.related_symbols)


def _title_tokens(title: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9\u4e00-\u9fff]+", title.lower())
    return set(tokens) - {"the", "and", "for", "with", "from", "after", "near", "over", "into"}


def _title_overlap(title_a: str, title_b: str) -> float:
    tokens_a = _title_tokens(title_a)
    tokens_b = _title_tokens(title_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _symbol_overlap(symbols_a: list[str], symbols_b: list[str]) -> int:
    return len(set(symbols_a) & set(symbols_b))


def _watchlist_hits_for_symbols(
    symbols: Iterable[str],
    watchlist_items: Iterable[WatchlistItem],
) -> list[str]:
    watchlist_items = list(watchlist_items)
    watchlist_by_symbol: dict[str, str] = {}
    for item in watchlist_items:
        symbol = item.symbol.strip().upper()
        display_name = item.display_name.strip()
        if not symbol or not display_name:
            continue
        watchlist_by_symbol[symbol] = display_name

    hits: list[str] = []
    seen_hits: set[str] = set()
    for symbol in symbols:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            continue
        display_name = watchlist_by_symbol.get(normalized_symbol)
        if display_name is None or display_name in seen_hits:
            continue
        hits.append(display_name)
        seen_hits.add(display_name)
    return hits


def _attach_watchlist_hits(
    cards: list[NewsFeedEventCardView],
    watchlist_items: Iterable[WatchlistItem],
) -> list[NewsFeedEventCardView]:
    watchlist_items = list(watchlist_items)
    return [
        card.model_copy(
            update={
                "watchlist_hits": _watchlist_hits_for_symbols(
                    [symbol for symbol in [card.primary_symbol, *card.related_symbols] if symbol],
                    watchlist_items,
                )
            }
        )
        for card in cards
    ]


def _should_fuse(card_a: NewsFeedEventCardView, card_b: NewsFeedEventCardView) -> bool:
    if card_a.event_type == "general" or card_b.event_type == "general":
        return False
    if card_a.event_type != card_b.event_type:
        return False
    if card_a.primary_symbol and card_a.primary_symbol == card_b.primary_symbol:
        return True
    if _symbol_overlap(card_a.related_symbols, card_b.related_symbols) >= 2:
        return True
    if _title_overlap(card_a.event_title, card_b.event_title) >= 0.5:
        return True
    return False


def _merge_cards(
    primary: NewsFeedEventCardView,
    secondary: NewsFeedEventCardView,
    *,
    max_news_items: int | None = 3,
) -> NewsFeedEventCardView:
    seen_ids: set[int] = {item.id for item in primary.news_items}
    merged_news = list(primary.news_items)
    for item in secondary.news_items:
        if item.id not in seen_ids:
            merged_news.append(item)
            seen_ids.add(item.id)
    merged_news.sort(
        key=_news_sort_key,
        reverse=True,
    )
    merged_symbols = list(dict.fromkeys(primary.related_symbols + secondary.related_symbols))[:5]
    merged_primary = primary.primary_symbol or secondary.primary_symbol
    merged_source_count = len({item.source_name for item in merged_news})
    merged_news_count = len(merged_news)
    return NewsFeedEventCardView(
        event_key=f"fused-{primary.event_key}-{secondary.event_key}",
        event_title=primary.event_title,
        event_summary=primary.event_summary or secondary.event_summary,
        event_type=primary.event_type,
        market=primary.market,
        sentiment_label=primary.sentiment_label,
        importance_score=max(primary.importance_score, secondary.importance_score),
        last_seen_at=max(
            filter(None, [primary.last_seen_at, secondary.last_seen_at]),
            default=None,
            key=lambda ts: ts.timestamp() if ts else 0.0,
        ),
        primary_symbol=merged_primary,
        related_symbols=merged_symbols,
        source_count=merged_source_count,
        news_count=merged_news_count,
        news_items=merged_news[:max_news_items] if max_news_items is not None else merged_news,
    )


def fuse_event_cards(
    cards: list[NewsFeedEventCardView],
    *,
    max_news_items: int | None = 3,
) -> list[NewsFeedEventCardView]:
    if len(cards) <= 1:
        return cards
    fused_indices: set[int] = set()
    result: list[NewsFeedEventCardView] = []
    for i, card in enumerate(cards):
        if i in fused_indices:
            continue
        current = card
        for j in range(i + 1, len(cards)):
            if j in fused_indices:
                continue
            if _should_fuse(current, cards[j]):
                current = _merge_cards(current, cards[j], max_news_items=max_news_items)
                fused_indices.add(j)
        result.append(current)
    return result


def build_event_cards(
    topics: list[TopicItemView],
    *,
    topic_news_map: dict[int, list[NewsItemSummary]],
    topic_mentions_map: dict[int, list[str]],
    max_news_items: int | None = 3,
) -> list[NewsFeedEventCardView]:
    weight_map = _source_weight_map()
    event_cards: list[NewsFeedEventCardView] = []
    for topic in topics:
        if not _qualifies_as_event(topic):
            continue

        news_items = sorted(
            topic_news_map.get(topic.id, []),
            key=_news_sort_key,
            reverse=True,
        )
        mention_counter = Counter(topic_mentions_map.get(topic.id, []))
        related_symbols = [
            symbol for symbol, _count in mention_counter.most_common(5)
        ] or topic.related_symbols[:5]
        primary_symbol = related_symbols[0] if related_symbols else None
        source_count = len({item.source_name for item in news_items})
        summary_seed = [topic.topic_title, topic.topic_summary or "", " ".join(topic.keywords)]
        summary_seed.extend(item.title for item in news_items[:2])
        source_weights = [
            weight_map.get(item.source_name, DEFAULT_SOURCE_WEIGHT) for item in news_items
        ]
        avg_weight = (
            sum(source_weights) / len(source_weights) if source_weights else DEFAULT_SOURCE_WEIGHT
        )
        adjusted_importance = round(topic.importance_score * avg_weight, 4)
        event_cards.append(
            NewsFeedEventCardView(
                event_key=f"topic-{topic.id}",
                event_title=topic.topic_title,
                event_summary=topic.topic_summary
                or (news_items[0].summary if news_items else None),
                event_type=_event_type_from_texts(summary_seed),
                market=topic.market,
                sentiment_label=topic.sentiment_label,
                importance_score=adjusted_importance,
                last_seen_at=topic.last_seen_at,
                primary_symbol=primary_symbol,
                related_symbols=related_symbols,
                source_count=source_count,
                news_count=len(news_items),
                news_items=news_items[:max_news_items]
                if max_news_items is not None
                else news_items,
            )
        )

    event_cards = fuse_event_cards(event_cards, max_news_items=max_news_items)

    event_cards.sort(
        key=lambda card: (
            _decayed_importance(card.importance_score, card.last_seen_at),
            card.last_seen_at.timestamp() if card.last_seen_at else 0.0,
            card.news_count,
        ),
        reverse=True,
    )
    return event_cards


def _keywords(raw_keywords: str | None) -> list[str]:
    if not raw_keywords:
        return []
    return [item.strip() for item in raw_keywords.split(",") if item.strip()]


def _topic_sentiment_label(score: float | None) -> str:
    if (score or 0.0) > 0.2:
        return "positive"
    if (score or 0.0) < -0.2:
        return "negative"
    return "neutral"


class NewsFeedLayoutService:
    def __init__(self, session) -> None:
        self.topic_repository = TopicRepository(session)
        self.news_repository = NewsRepository(session)
        self.watchlist_repository = WatchlistRepository(session)

    def _stream_editorial_scores(
        self,
        stream_items: list[NewsItemSummary],
        topic_views: list[NewsFeedTopicView],
        topic_news_map: dict[int, list[NewsItemSummary]],
        topic_mentions_map: dict[int, list[str]],
    ) -> list[NewsItemSummary]:
        weight_map = _source_weight_map()
        news_to_topic: dict[int, tuple[float, list[str]]] = {}
        for topic in topic_views:
            topic_importance = topic.importance_score
            topic_symbols = topic_mentions_map.get(topic.id, [])
            for item in topic_news_map.get(topic.id, []):
                if item.id not in news_to_topic or news_to_topic[item.id][0] < topic_importance:
                    news_to_topic[item.id] = (topic_importance, topic_symbols)

        for item in stream_items:
            topic_importance, topic_symbols = news_to_topic.get(item.id, (0.0, []))
            source_weight = weight_map.get(item.source_name, DEFAULT_SOURCE_WEIGHT)
            freshness = _decayed_importance(1.0, item.published_at or item.fetched_at)
            has_mentions = EDITORIAL_MENTION_BONUS if topic_symbols else 0.0
            official_bonus = EDITORIAL_OFFICIAL_BONUS if has_official_signal(item.source_name) else 0.0
            editorial_score = round(
                topic_importance * EDITORIAL_TOPIC_WEIGHT
                + (source_weight / 1.2) * EDITORIAL_SOURCE_WEIGHT
                + freshness * EDITORIAL_FRESHNESS_WEIGHT
                + has_mentions
                + official_bonus,
                4,
            )
            item.editorial_score = editorial_score

        stream_items.sort(key=lambda x: x.editorial_score or 0.0, reverse=True)
        return stream_items

    def _collect_topic_context(
        self,
        *,
        market: str | None = None,
    ) -> tuple[list[NewsFeedTopicView], dict[int, list[NewsItemSummary]], dict[int, list[str]]]:
        topics = self.topic_repository.list_all()
        topic_ids = [t.id for t in topics]

        batch_news = self.topic_repository.batch_news_for_topics(topic_ids)
        batch_symbols = self.topic_repository.batch_related_symbols(topic_ids, market=market)

        topic_views: list[NewsFeedTopicView] = []
        topic_news_map: dict[int, list[NewsItemSummary]] = {}
        topic_mentions_map: dict[int, list[str]] = {}

        for topic in topics:
            news_items = batch_news.get(topic.id, [])
            if market:
                news_items = [item for item in news_items if item.market == market]
            if not news_items:
                continue

            related_symbols = batch_symbols.get(topic.id, [])
            topic_views.append(
                NewsFeedTopicView(
                    id=topic.id,
                    topic_title=topic.topic_title,
                    topic_summary=topic.topic_summary,
                    keywords=_keywords(topic.keywords),
                    market=news_items[0].market,
                    sentiment_label=_topic_sentiment_label(topic.sentiment_score),
                    importance_score=topic.importance_score or 0.0,
                    news_count=len(news_items),
                    last_seen_at=topic.last_seen_at or news_items[0].fetched_at,
                    related_symbols=related_symbols,
                )
            )
            topic_news_map[topic.id] = [
                NewsItemSummary.model_validate(item, from_attributes=True) for item in news_items
            ]
            topic_mentions_map[topic.id] = related_symbols

        topic_views.sort(
            key=lambda item: (item.importance_score, item.last_seen_at.timestamp()), reverse=True
        )
        return topic_views, topic_news_map, topic_mentions_map

    @staticmethod
    def _build_event_detail(
        event_key: str,
        *,
        topic_views: list[NewsFeedTopicView],
        topic_news_map: dict[int, list[NewsItemSummary]],
        topic_mentions_map: dict[int, list[str]],
        watchlist_items: list[WatchlistItem] | None = None,
    ) -> NewsEventDetailView | None:
        watchlist_items = watchlist_items or []
        cards = build_event_cards(
            topic_views,
            topic_news_map=topic_news_map,
            topic_mentions_map=topic_mentions_map,
        )
        cards = _attach_watchlist_hits(cards, watchlist_items)
        event_card = next((card for card in cards if card.event_key == event_key), None)
        if event_card is None:
            return None

        full_cards = build_event_cards(
            topic_views,
            topic_news_map=topic_news_map,
            topic_mentions_map=topic_mentions_map,
            max_news_items=None,
        )
        full_cards = _attach_watchlist_hits(full_cards, watchlist_items)
        full_event_card = next((card for card in full_cards if card.event_key == event_key), None)
        if full_event_card is None:
            return None

        full_news_items = sorted(full_event_card.news_items, key=_news_sort_key, reverse=True)
        payload = event_card.model_dump()
        payload["news_count"] = len(full_news_items)
        payload["source_count"] = len({item.source_name for item in full_news_items})
        payload["news_items"] = full_news_items
        return NewsEventDetailView(
            **payload,
        )

    def get_event_detail(self, event_key: str) -> NewsEventDetailView | None:
        topic_views, topic_news_map, topic_mentions_map = self._collect_topic_context()
        watchlist_items = self.watchlist_repository.list_all()
        return self._build_event_detail(
            event_key,
            topic_views=topic_views,
            topic_news_map=topic_news_map,
            topic_mentions_map=topic_mentions_map,
            watchlist_items=watchlist_items,
        )

    def build(
        self,
        *,
        market: str | None = None,
        limit_events: int = 6,
        limit_topics: int = 6,
        limit_stream: int = 24,
    ) -> NewsFeedLayoutView:
        stream_items = [
            NewsItemSummary.model_validate(item, from_attributes=True)
            for item in self.news_repository.list_recent(limit=limit_stream, market=market)
        ]

        topic_views, topic_news_map, topic_mentions_map = self._collect_topic_context(market=market)
        watchlist_items = self.watchlist_repository.list_all()
        event_cards = build_event_cards(
            topic_views, topic_news_map=topic_news_map, topic_mentions_map=topic_mentions_map
        )
        event_cards = _attach_watchlist_hits(event_cards, watchlist_items)

        scored_stream = self._stream_editorial_scores(
            stream_items, topic_views, topic_news_map, topic_mentions_map
        )

        return NewsFeedLayoutView(
            events=event_cards[:limit_events],
            topics=topic_views[:limit_topics],
            stream=scored_stream,
        )
