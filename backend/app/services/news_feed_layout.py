from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

from app.repositories.news_repository import NewsRepository
from app.repositories.topic_repository import TopicRepository
from app.schemas.news import (
    NewsFeedEventCardView,
    NewsFeedLayoutView,
    NewsFeedTopicView,
    NewsItemSummary,
)
from app.schemas.topic import TopicItemView

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


def _qualifies_as_event(topic: TopicItemView) -> bool:
    return topic.importance_score >= 0.55 or topic.news_count >= 2 or bool(topic.related_symbols)


def build_event_cards(
    topics: list[TopicItemView],
    *,
    topic_news_map: dict[int, list[NewsItemSummary]],
    topic_mentions_map: dict[int, list[str]],
    max_news_items: int = 3,
) -> list[NewsFeedEventCardView]:
    weight_map = _source_weight_map()
    event_cards: list[NewsFeedEventCardView] = []
    for topic in topics:
        if not _qualifies_as_event(topic):
            continue

        news_items = sorted(
            topic_news_map.get(topic.id, []),
            key=lambda item: (item.published_at is None, item.published_at, item.fetched_at),
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
                news_items=news_items[:max_news_items],
            )
        )

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
        event_cards = build_event_cards(
            topic_views, topic_news_map=topic_news_map, topic_mentions_map=topic_mentions_map
        )

        return NewsFeedLayoutView(
            events=event_cards[:limit_events],
            topics=topic_views[:limit_topics],
            stream=stream_items,
        )
