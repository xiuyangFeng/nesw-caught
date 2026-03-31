from datetime import datetime, timezone
from unittest.mock import patch
import math
from types import SimpleNamespace

from app.schemas.news import NewsItemSummary
from app.schemas.topic import TopicItemView
from app.services.news_feed_layout import (
    NewsFeedLayoutService,
    build_event_cards,
    fuse_event_cards,
    _attach_watchlist_hits,
    _watchlist_hits_for_symbols,
    _event_type_from_texts,
    _title_overlap,
    _should_fuse,
    _merge_cards,
    NewsFeedEventCardView,
)


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


def test_watchlist_hits_follow_primary_symbol_then_related_symbols_and_skip_blank_labels() -> None:
    watchlist_items = [
        SimpleNamespace(symbol="SMCI", display_name="Super Micro"),
        SimpleNamespace(symbol="NVDA", display_name="NVIDIA"),
        SimpleNamespace(symbol="AMD", display_name="   "),
        SimpleNamespace(symbol="TSLA", display_name="Tesla"),
    ]

    hits = _watchlist_hits_for_symbols(["NVDA", "SMCI", "NVDA", "AMD", "TSLA"], watchlist_items)

    assert hits == ["NVIDIA", "Super Micro", "Tesla"]


def test_attach_watchlist_hits_populates_event_cards() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    card = _event_card(
        event_key="t-1",
        event_title="NVIDIA AI Chip Launch",
        primary_symbol="NVDA",
        related_symbols=["SMCI", "NVDA"],
        last_seen_at=now,
    )
    watchlist_items = [
        SimpleNamespace(symbol="NVDA", display_name="NVIDIA"),
        SimpleNamespace(symbol="SMCI", display_name="Super Micro"),
    ]

    [updated] = _attach_watchlist_hits([card], watchlist_items)

    assert updated.watchlist_hits == ["NVIDIA", "Super Micro"]


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
            title="NVIDIA Chip Announcement",
            summary="Event from primary tier source.",
            keywords=["nvidia", "chip"],
            importance_score=0.8,
            last_seen_at=now,
            related_symbols=["NVDA"],
            sentiment_label="positive",
        ),
        _topic(
            2,
            title="Apple Product Update",
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

    primary_card = next(c for c in cards if c.event_title == "NVIDIA Chip Announcement")
    unknown_card = next(c for c in cards if c.event_title == "Apple Product Update")
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


def _event_card(
    *,
    event_key: str,
    event_title: str,
    event_type: str = "product",
    primary_symbol: str | None = None,
    related_symbols: list[str] | None = None,
    importance_score: float = 0.8,
    last_seen_at: datetime | None = None,
    news_items: list[NewsItemSummary] | None = None,
) -> NewsFeedEventCardView:
    now = last_seen_at or datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    return NewsFeedEventCardView(
        event_key=event_key,
        event_title=event_title,
        event_summary="Test summary",
        event_type=event_type,
        market="us",
        sentiment_label="neutral",
        importance_score=importance_score,
        last_seen_at=now,
        primary_symbol=primary_symbol,
        related_symbols=related_symbols or [],
        source_count=1,
        news_count=len(news_items) if news_items else 0,
        news_items=news_items or [],
    )


def test_title_overlap_detects_similar_titles() -> None:
    assert _title_overlap("NVIDIA AI chip launch", "NVIDIA AI chip release") >= 0.5
    assert _title_overlap("Apple earnings beat", "Fed rate decision") < 0.3


def test_should_fuse_same_primary_symbol() -> None:
    a = _event_card(event_key="t-1", event_title="NVIDIA chip launch", primary_symbol="NVDA")
    b = _event_card(event_key="t-2", event_title="NVIDIA supply update", primary_symbol="NVDA")
    assert _should_fuse(a, b) is True


def test_should_fuse_symbol_overlap() -> None:
    a = _event_card(
        event_key="t-1", event_title="Chip supply", related_symbols=["NVDA", "AMD", "TSMC"]
    )
    b = _event_card(
        event_key="t-2", event_title="Chip demand", related_symbols=["NVDA", "AMD", "INTC"]
    )
    assert _should_fuse(a, b) is True


def test_should_not_fuse_different_event_types() -> None:
    a = _event_card(
        event_key="t-1", event_title="Rate decision", event_type="macro", primary_symbol="NVDA"
    )
    b = _event_card(
        event_key="t-2", event_title="NVIDIA launch", event_type="product", primary_symbol="NVDA"
    )
    assert _should_fuse(a, b) is False


def test_should_not_fuse_general_events() -> None:
    a = _event_card(event_key="t-1", event_title="Company update", event_type="general")
    b = _event_card(event_key="t-2", event_title="Company update", event_type="general")
    assert _should_fuse(a, b) is False


def test_fuse_event_cards_merges_duplicate_events() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    news_a = [
        _news_item(1, title="NVIDIA chip story A", summary="s", source_name="WSJ", published_at=now)
    ]
    news_b = [
        _news_item(
            2, title="NVIDIA chip story B", summary="s", source_name="Reuters", published_at=now
        )
    ]
    a = _event_card(
        event_key="t-1",
        event_title="NVIDIA AI Chip Launch",
        event_type="product",
        primary_symbol="NVDA",
        related_symbols=["NVDA", "SMCI"],
        importance_score=0.9,
        news_items=news_a,
    )
    b = _event_card(
        event_key="t-2",
        event_title="NVIDIA AI Platform Release",
        event_type="product",
        primary_symbol="NVDA",
        related_symbols=["NVDA", "AMD"],
        importance_score=0.7,
        news_items=news_b,
    )
    result = fuse_event_cards([a, b])
    assert len(result) == 1
    assert result[0].primary_symbol == "NVDA"
    assert "NVDA" in result[0].related_symbols
    assert "SMCI" in result[0].related_symbols
    assert result[0].news_count == 2
    assert len(result[0].news_items) == 2
    assert result[0].importance_score == 0.9


def test_fuse_event_cards_keeps_independent_events() -> None:
    a = _event_card(
        event_key="t-1",
        event_title="Apple earnings beat",
        event_type="earnings",
        primary_symbol="AAPL",
    )
    b = _event_card(
        event_key="t-2", event_title="Fed rate decision", event_type="macro", primary_symbol=None
    )
    result = fuse_event_cards([a, b])
    assert len(result) == 2


def test_merge_cards_preserves_higher_importance() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    a = _event_card(
        event_key="t-1",
        event_title="High",
        importance_score=0.95,
        last_seen_at=now,
        primary_symbol="NVDA",
    )
    b = _event_card(
        event_key="t-2",
        event_title="Low",
        importance_score=0.6,
        last_seen_at=now,
        primary_symbol="NVDA",
    )
    merged = _merge_cards(a, b)
    assert merged.importance_score == 0.95
    assert "fused-" in merged.event_key


def test_merge_cards_recomputes_unique_story_and_source_counts() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    shared_story = _news_item(
        101,
        title="Shared NVIDIA story",
        summary="s",
        source_name="Reuters",
        published_at=now,
    )
    exclusive_story = _news_item(
        102,
        title="Exclusive follow-up",
        summary="s",
        source_name="Bloomberg",
        published_at=now,
    )
    a = _event_card(
        event_key="t-1",
        event_title="NVIDIA launch",
        primary_symbol="NVDA",
        news_items=[shared_story],
    )
    b = _event_card(
        event_key="t-2",
        event_title="NVIDIA platform release",
        primary_symbol="NVDA",
        news_items=[shared_story, exclusive_story],
    )

    merged = _merge_cards(a, b)

    assert merged.news_count == 2
    assert merged.source_count == 2
    assert len(merged.news_items) == 2


def test_get_event_detail_reconstructs_fused_event_with_full_news_items() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    first = _topic(
        1,
        title="NVIDIA AI Chip Launch",
        summary="Primary launch story.",
        keywords=["nvidia", "chip", "launch"],
        importance_score=0.91,
        last_seen_at=now,
        related_symbols=["NVDA", "SMCI"],
        sentiment_label="positive",
    )
    second = _topic(
        2,
        title="NVIDIA AI Platform Release",
        summary="Follow-up platform release.",
        keywords=["nvidia", "platform", "release"],
        importance_score=0.88,
        last_seen_at=now,
        related_symbols=["NVDA", "AMD"],
        sentiment_label="positive",
    )
    topic_views = [first, second]
    topic_news_map = {
        1: [
            _news_item(1, title="Story A", summary="A", source_name="Reuters", published_at=now),
            _news_item(2, title="Story B", summary="B", source_name="Bloomberg", published_at=now),
        ],
        2: [
            _news_item(3, title="Story C", summary="C", source_name="WSJ", published_at=now),
            _news_item(4, title="Story D", summary="D", source_name="The Verge", published_at=now),
        ],
    }
    topic_mentions_map = {
        1: ["NVDA", "SMCI"],
        2: ["NVDA", "AMD"],
    }

    cards = build_event_cards(
        topic_views,
        topic_news_map=topic_news_map,
        topic_mentions_map=topic_mentions_map,
    )
    fused_key = cards[0].event_key

    detail = NewsFeedLayoutService._build_event_detail(
        fused_key,
        topic_views=topic_views,
        topic_news_map=topic_news_map,
        topic_mentions_map=topic_mentions_map,
    )

    assert detail is not None
    assert detail.event_key == fused_key
    assert detail.news_count == 4
    assert len(detail.news_items) == 4


def test_get_event_detail_sorts_mixed_published_and_fetched_timestamps_with_null_published_last() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    topic = _topic(
        1,
        title="AI Chip Launch",
        summary="Launch follow-up.",
        keywords=["ai", "chip", "launch"],
        importance_score=0.91,
        last_seen_at=now,
        related_symbols=["NVDA"],
        sentiment_label="positive",
    )
    published_latest = _news_item(
        10,
        title="Published latest",
        summary="Newest published story.",
        source_name="Reuters",
        published_at=datetime(2026, 3, 28, 9, 5, tzinfo=timezone.utc),
    )
    fetched_only = _news_item(
        11,
        title="Fetched only",
        summary="No published_at, but fetched later.",
        source_name="Bloomberg",
        published_at=now,
    )
    fetched_only.published_at = None
    fetched_only.fetched_at = datetime(2026, 3, 28, 9, 30, tzinfo=timezone.utc)
    published_older = _news_item(
        12,
        title="Published older",
        summary="Older published story.",
        source_name="WSJ",
        published_at=datetime(2026, 3, 28, 8, 50, tzinfo=timezone.utc),
    )

    detail = NewsFeedLayoutService._build_event_detail(
        "topic-1",
        topic_views=[topic],
        topic_news_map={1: [fetched_only, published_older, published_latest]},
        topic_mentions_map={1: ["NVDA"]},
    )

    assert detail is not None
    assert [item.title for item in detail.news_items] == [
        "Published latest",
        "Published older",
        "Fetched only",
    ]


def test_get_event_detail_does_not_truncate_large_event_news_items() -> None:
    now = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    topic = _topic(
        1,
        title="Large Event",
        summary="Large event summary.",
        keywords=["large", "event"],
        importance_score=0.91,
        last_seen_at=now,
        related_symbols=["NVDA"],
    )
    news_items = [
        _news_item(
            news_id,
            title=f"Story {news_id}",
            summary="Bulk story.",
            source_name=f"Source-{news_id % 7}",
            published_at=datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc),
        )
        for news_id in range(1, 506)
    ]

    detail = NewsFeedLayoutService._build_event_detail(
        "topic-1",
        topic_views=[topic],
        topic_news_map={1: news_items},
        topic_mentions_map={1: ["NVDA"]},
    )

    assert detail is not None
    assert detail.news_count == 505
    assert detail.source_count == 7
    assert len(detail.news_items) == 505
