from datetime import datetime, timezone
from unittest.mock import patch
import math

from app.schemas.news import NewsItemSummary
from app.schemas.topic import TopicItemView
from app.services.news_feed_layout import build_event_cards, _event_type_from_texts


def _news_item(
    news_id: int,
    *,
    title: str,
    summary: str,
    source_name: str,
    published_at: datetime,
    sentiment_label: str = "neutral",
    market: str = "us",
) -> NewsItemSummary:
    return NewsItemSummary(
        id=news_id,
        title=title,
        summary=summary,
        source_name=source_name,
        canonical_url=f"https://example.com/{news_id}",
        market=market,
        sentiment_label=sentiment_label,
        published_at=published_at,
        fetched_at=published_at,
    )


def _topic(
    topic_id: int,
    *,
    title: str,
    summary: str,
    keywords: list[str],
    importance_score: float,
    last_seen_at: datetime,
    related_symbols: list[str],
    sentiment_label: str = "neutral",
    market: str = "us",
    news_count: int = 2,
) -> TopicItemView:
    return TopicItemView(
        id=topic_id,
        topic_title=title,
        topic_summary=summary,
        keywords=keywords,
        market=market,
        sentiment_label=sentiment_label,
        importance_score=importance_score,
        news_count=news_count,
        last_seen_at=last_seen_at,
        related_symbols=related_symbols,
    )


def test_build_event_cards_keeps_only_qualifying_topics_and_sorts_by_importance_then_freshness() -> (
    None
):
    older = datetime(2026, 3, 28, 7, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 3, 28, 8, 0, tzinfo=timezone.utc)
    topics = [
        _topic(
            1,
            title="AI Chip Launch",
            summary="NVIDIA launched a new AI platform.",
            keywords=["nvidia", "chip", "launch"],
            importance_score=0.91,
            last_seen_at=newer,
            related_symbols=["NVDA", "SMCI"],
            sentiment_label="positive",
        ),
        _topic(
            2,
            title="Quiet Topic",
            summary="Low-signal coverage.",
            keywords=["misc"],
            importance_score=0.3,
            last_seen_at=older,
            related_symbols=[],
            news_count=1,
        ),
        _topic(
            3,
            title="Fed Policy Watch",
            summary="Rate outlook remains in focus.",
            keywords=["fed", "rate", "policy"],
            importance_score=0.72,
            last_seen_at=older,
            related_symbols=[],
        ),
    ]
    topic_news_map = {
        1: [
            _news_item(
                11,
                title="NVIDIA launches new AI chip platform",
                summary="Launch headline.",
                source_name="Bloomberg",
                sentiment_label="positive",
                published_at=newer,
            ),
            _news_item(
                12,
                title="Suppliers rally after NVIDIA chip release",
                summary="Supplier reaction.",
                source_name="Reuters",
                sentiment_label="positive",
                published_at=older,
            ),
        ],
        2: [
            _news_item(
                21,
                title="Quiet update",
                summary="Minor note.",
                source_name="Reuters",
                published_at=older,
            )
        ],
        3: [
            _news_item(
                31,
                title="Fed officials signal policy remains unchanged",
                summary="Macro update.",
                source_name="WSJ",
                published_at=older,
            )
        ],
    }
    topic_mentions_map = {
        1: ["NVDA", "SMCI", "NVDA"],
        2: [],
        3: [],
    }

    event_cards = build_event_cards(
        topics, topic_news_map=topic_news_map, topic_mentions_map=topic_mentions_map
    )

    assert [item.event_title for item in event_cards] == ["AI Chip Launch", "Fed Policy Watch"]
    assert event_cards[0].event_type == "product"
    assert event_cards[0].primary_symbol == "NVDA"
    assert event_cards[0].related_symbols == ["NVDA", "SMCI"]


def test_build_event_cards_limits_story_mounts_and_classifies_macro_and_supply_chain_patterns() -> (
    None
):
    now = datetime(2026, 3, 28, 9, 0, tzinfo=timezone.utc)
    topics = [
        _topic(
            10,
            title="Fed Policy Watch",
            summary="Markets await inflation and rate signals.",
            keywords=["fed", "policy", "rate", "inflation"],
            importance_score=0.82,
            last_seen_at=now,
            related_symbols=[],
        ),
        _topic(
            11,
            title="Apple Supplier Demand",
            summary="Suppliers warn of softer orders and shipments.",
            keywords=["apple", "supplier", "orders", "shipment"],
            importance_score=0.8,
            last_seen_at=now,
            related_symbols=["AAPL"],
        ),
    ]
    topic_news_map = {
        10: [
            _news_item(
                i, title=f"Fed story {i}", summary="Macro", source_name="WSJ", published_at=now
            )
            for i in range(100, 104)
        ],
        11: [
            _news_item(
                200,
                title="Apple supplier flags softer demand",
                summary="Supply chain warning",
                source_name="Reuters",
                published_at=now,
            )
        ],
    }

    event_cards = build_event_cards(
        topics, topic_news_map=topic_news_map, topic_mentions_map={10: [], 11: ["AAPL"]}
    )

    assert event_cards[0].event_type == "macro"
    assert event_cards[0].news_count == 4
    assert len(event_cards[0].news_items) == 3
    assert event_cards[1].event_type == "supply_chain"


def test_chinese_event_type_patterns_classify_correctly() -> None:
    assert _event_type_from_texts(["公司财报营收超预期 盈利大增"]) == "earnings"
    assert _event_type_from_texts(["监管部门开出反垄断罚单"]) == "regulation"
    assert _event_type_from_texts(["股价暴涨 异动拉升 飙升"]) == "market_move"
    assert _event_type_from_texts(["公司收购并购合并重组"]) == "mna"
    assert _event_type_from_texts(["新品发布 上线旗舰产品"]) == "product"
    assert _event_type_from_texts(["供应链产能出货订单交付"]) == "supply_chain"
    assert _event_type_from_texts(["宏观通胀 加息 利率"]) == "macro"
    assert _event_type_from_texts(["公司日常运营情况更新"]) == "general"


def test_source_weighting_adjusts_importance_by_tier() -> None:
    now = datetime(2026, 3, 28, 9, 0, tzinfo=timezone.utc)
    topics = [
        _topic(
            1,
            title="Primary Source Event",
            summary="Event from primary tier source.",
            keywords=["nvidia", "chip"],
            importance_score=0.8,
            last_seen_at=now,
            related_symbols=["NVDA"],
            sentiment_label="positive",
        ),
        _topic(
            2,
            title="Unknown Source Event",
            summary="Event from unknown source.",
            keywords=["apple", "product"],
            importance_score=0.8,
            last_seen_at=now,
            related_symbols=["AAPL"],
            sentiment_label="positive",
        ),
    ]
    fake_sources = [
        type("Src", (), {"name": "WSJ World News", "tier": "primary"})(),
        type("Src", (), {"name": "The Verge", "tier": "primary"})(),
        type("Src", (), {"name": "36Kr", "tier": "primary"})(),
        type("Src", (), {"name": "SEC Press Releases", "tier": "primary"})(),
        type("Src", (), {"name": "CLS Telegraph", "tier": "primary"})(),
        type("Src", (), {"name": "MiniMax News", "tier": "primary"})(),
        type("Src", (), {"name": "Zhipu AI News", "tier": "primary"})(),
    ]
    with patch("app.services.news_ingestion.load_sources", return_value=fake_sources):
        topic_news_map = {
            1: [
                _news_item(
                    1,
                    title="WSJ story",
                    summary="s",
                    source_name="WSJ World News",
                    published_at=now,
                )
            ],
            2: [
                _news_item(
                    2,
                    title="Random story",
                    summary="s",
                    source_name="Unknown Blog",
                    published_at=now,
                )
            ],
        }
        topic_mentions_map = {1: ["NVDA"], 2: ["AAPL"]}
        cards = build_event_cards(
            topics, topic_news_map=topic_news_map, topic_mentions_map=topic_mentions_map
        )

    primary_card = next(c for c in cards if c.event_title == "Primary Source Event")
    unknown_card = next(c for c in cards if c.event_title == "Unknown Source Event")
    assert primary_card.importance_score > unknown_card.importance_score


def test_time_decay_sorts_recent_events_before_older_ones() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    one_hour_ago = datetime(2026, 3, 28, 9, 0, tzinfo=timezone.utc)
    two_days_ago = datetime(2026, 3, 26, 10, 0, tzinfo=timezone.utc)
    topics = [
        _topic(
            1,
            title="Recent Event",
            summary="Recent.",
            keywords=["nvidia", "chip"],
            importance_score=0.8,
            last_seen_at=one_hour_ago,
            related_symbols=["NVDA"],
        ),
        _topic(
            2,
            title="Old Event",
            summary="Old.",
            keywords=["apple", "supply"],
            importance_score=0.8,
            last_seen_at=two_days_ago,
            related_symbols=["AAPL"],
        ),
    ]
    fake_sources = [
        type("Src", (), {"name": "WSJ World News", "tier": "primary"})(),
        type("Src", (), {"name": "The Verge", "tier": "primary"})(),
        type("Src", (), {"name": "36Kr", "tier": "primary"})(),
        type("Src", (), {"name": "SEC Press Releases", "tier": "primary"})(),
        type("Src", (), {"name": "CLS Telegraph", "tier": "primary"})(),
        type("Src", (), {"name": "MiniMax News", "tier": "primary"})(),
        type("Src", (), {"name": "Zhipu AI News", "tier": "primary"})(),
    ]
    with patch("app.services.news_ingestion.load_sources", return_value=fake_sources):
        topic_news_map = {
            1: [
                _news_item(
                    1,
                    title="Recent",
                    summary="s",
                    source_name="WSJ World News",
                    published_at=one_hour_ago,
                )
            ],
            2: [
                _news_item(
                    2,
                    title="Old",
                    summary="s",
                    source_name="WSJ World News",
                    published_at=two_days_ago,
                )
            ],
        }
        topic_mentions_map = {1: ["NVDA"], 2: ["AAPL"]}
        cards = build_event_cards(
            topics, topic_news_map=topic_news_map, topic_mentions_map=topic_mentions_map
        )

    assert cards[0].event_title == "Recent Event"
    assert cards[1].event_title == "Old Event"

    one_hour_decay = math.exp(-0.03 * 1)
    two_day_decay = math.exp(-0.03 * 48)
    assert cards[0].importance_score * one_hour_decay > cards[1].importance_score * two_day_decay
