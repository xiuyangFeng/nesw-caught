from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.source_health import SourceHealth
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.models.watchlist_item import WatchlistItem
from app.main import app
from app.services.event_bus import EventBusStatus
from app.services.news_ingestion import SourceDefinition


def test_news_runtime_returns_market_and_source_health_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.news_runtime._utc_now",
        lambda: datetime(2026, 3, 25, 2, 40, tzinfo=timezone.utc),
    )
    source_health = SourceHealth(
        source_name="Example Source",
        market="us",
        source_type="rss",
        last_success_at=datetime(2026, 3, 25, 2, 40, tzinfo=timezone.utc),
        last_failure_at=None,
        consecutive_failures=0,
        total_fetches=1,
        total_failures=0,
        avg_latency_ms=320.0,
        is_disabled=False,
    )
    monkeypatch.setattr(
        "app.services.news_runtime.load_sources",
        lambda: [
            SourceDefinition(
                name="Example Source",
                source_type="rss",
                url="https://example.com/rss",
                market="us",
                markets=["us"],
                tier="primary",
            )
        ],
    )
    monkeypatch.setattr(
        "app.repositories.source_health_repository.SourceHealthRepository.list_all",
        lambda self: [source_health],
    )
    monkeypatch.setattr(
        "app.services.news_runtime.get_event_bus",
        lambda: type(
            "FakeBus",
            (),
            {
                "get_status": staticmethod(
                    lambda: EventBusStatus(
                        backend="memory",
                        status="ok",
                        redis_enabled=False,
                        last_published_at=datetime(2026, 3, 25, 2, 39, 55, tzinfo=timezone.utc),
                        last_event_name="news.created",
                    )
                )
            },
        )(),
    )

    client = TestClient(app)
    source_name = "Example Source"
    url_hash = "test-news-runtime-contract"
    news_created_at = datetime(2026, 3, 25, 2, 39, 40, tzinfo=timezone.utc)
    published_at = datetime(2026, 3, 25, 2, 35, tzinfo=timezone.utc)

    with SessionLocal() as session:
        session.add(
            NewsItem(
                source_name=source_name,
                source_url="https://example.com/rss",
                title="Runtime test story",
                summary="runtime payload fixture",
                canonical_url="https://example.com/runtime-test-story",
                url_hash=url_hash,
                market="us",
                language="en",
                sentiment_label=None,
                sentiment_score=None,
                published_at=published_at,
                fetched_at=news_created_at,
                ingest_status="ingested",
            )
        )
        session.commit()

    def cleanup() -> None:
        with SessionLocal() as session:
            session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
            session.commit()

    try:
        response = client.get("/api/news/runtime")

        assert response.status_code == 200
        payload = response.json()
        assert payload == {
            "feed_status": "live",
            "last_refresh_finished_at": "2026-03-25T02:40:00Z",
            "last_news_created_at": "2026-03-25T02:39:40Z",
            "last_incremental_event_at": "2026-03-25T02:39:55Z",
            "degraded_market_count": 0,
            "markets": [
                {
                    "market": "us",
                    "status": "live",
                    "mode": "primary",
                    "last_primary_success_at": "2026-03-25T02:40:00Z",
                    "last_news_created_at": "2026-03-25T02:39:40Z",
                    "degraded_reason": None,
                }
            ],
            "sources": [
                {
                    "source_name": "Example Source",
                    "market": "us",
                    "tier": "primary",
                    "status": "ok",
                    "last_attempt_at": "2026-03-25T02:40:00Z",
                    "last_success_at": "2026-03-25T02:40:00Z",
                    "consecutive_failures": 0,
                    "avg_fetch_latency_ms": 320.0,
                    "latest_news_published_at": "2026-03-25T02:35:00Z",
                    "latest_news_fetched_at": "2026-03-25T02:39:40Z",
                    "last_error": None,
                }
            ],
        }
    finally:
        cleanup()


def test_news_runtime_maps_runtime_statuses_per_spec(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.news_runtime._utc_now",
        lambda: datetime(2026, 3, 25, 2, 40, tzinfo=timezone.utc),
    )
    source_rows = [
        SourceHealth(
            source_name="US Primary",
            market="us",
            source_type="rss",
            last_success_at=datetime(2026, 3, 25, 2, 20, tzinfo=timezone.utc),
            last_failure_at=None,
            consecutive_failures=0,
            total_fetches=4,
            total_failures=0,
            avg_latency_ms=210.0,
            is_disabled=False,
        ),
        SourceHealth(
            source_name="HK Primary",
            market="hk",
            source_type="rss",
            last_success_at=datetime(2026, 3, 25, 1, 50, tzinfo=timezone.utc),
            last_failure_at=datetime(2026, 3, 25, 2, 35, tzinfo=timezone.utc),
            consecutive_failures=2,
            total_fetches=7,
            total_failures=2,
            avg_latency_ms=500.0,
            is_disabled=False,
        ),
        SourceHealth(
            source_name="HK Secondary",
            market="hk",
            source_type="rss",
            last_success_at=datetime(2026, 3, 25, 2, 38, tzinfo=timezone.utc),
            last_failure_at=None,
            consecutive_failures=0,
            total_fetches=3,
            total_failures=0,
            avg_latency_ms=260.0,
            is_disabled=False,
        ),
        SourceHealth(
            source_name="CN Primary",
            market="cn",
            source_type="rss",
            last_success_at=datetime(2026, 3, 25, 1, 40, tzinfo=timezone.utc),
            last_failure_at=datetime(2026, 3, 25, 2, 39, tzinfo=timezone.utc),
            consecutive_failures=4,
            total_fetches=9,
            total_failures=4,
            avg_latency_ms=610.0,
            is_disabled=False,
        ),
    ]
    monkeypatch.setattr(
        "app.services.news_runtime.load_sources",
        lambda: [
            SourceDefinition(
                name="US Primary",
                source_type="rss",
                url="https://example.com/us-primary",
                market="us",
                markets=["us"],
                tier="primary",
                cadence_seconds=300,
            ),
            SourceDefinition(
                name="HK Primary",
                source_type="rss",
                url="https://example.com/hk-primary",
                market="hk",
                markets=["hk"],
                tier="primary",
                cadence_seconds=300,
            ),
            SourceDefinition(
                name="HK Secondary",
                source_type="rss",
                url="https://example.com/hk-secondary",
                market="hk",
                markets=["hk"],
                tier="secondary",
                cadence_seconds=300,
            ),
            SourceDefinition(
                name="CN Primary",
                source_type="rss",
                url="https://example.com/cn-primary",
                market="cn",
                markets=["cn"],
                tier="primary",
                cadence_seconds=300,
            ),
        ],
    )
    monkeypatch.setattr(
        "app.repositories.source_health_repository.SourceHealthRepository.list_all",
        lambda self: source_rows,
    )
    monkeypatch.setattr(
        "app.services.news_runtime.get_event_bus",
        lambda: type(
            "FakeBus",
            (),
            {
                "get_status": staticmethod(
                    lambda: EventBusStatus(
                        backend="memory",
                        status="ok",
                        redis_enabled=False,
                        last_published_at=datetime(2026, 3, 25, 2, 38, 30, tzinfo=timezone.utc),
                        last_event_name="news.created",
                    )
                )
            },
        )(),
    )

    client = TestClient(app)
    url_hashes = [
        "test-runtime-us-delayed",
        "test-runtime-hk-secondary",
    ]

    with SessionLocal() as session:
        session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
        session.add_all(
            [
                NewsItem(
                    source_name="US Primary",
                    source_url="https://example.com/us-primary",
                    title="US delayed market item",
                    summary="fixture",
                    canonical_url="https://example.com/us-delayed",
                    url_hash=url_hashes[0],
                    market="us",
                    language="en",
                    sentiment_label=None,
                    sentiment_score=None,
                    published_at=datetime(2026, 3, 25, 1, 55, tzinfo=timezone.utc),
                    fetched_at=datetime(2026, 3, 25, 1, 59, tzinfo=timezone.utc),
                    ingest_status="ingested",
                ),
                NewsItem(
                    source_name="HK Secondary",
                    source_url="https://example.com/hk-secondary",
                    title="HK secondary market item",
                    summary="fixture",
                    canonical_url="https://example.com/hk-secondary-item",
                    url_hash=url_hashes[1],
                    market="hk",
                    language="zh",
                    sentiment_label=None,
                    sentiment_score=None,
                    published_at=datetime(2026, 3, 25, 2, 35, tzinfo=timezone.utc),
                    fetched_at=datetime(2026, 3, 25, 2, 38, tzinfo=timezone.utc),
                    ingest_status="ingested",
                ),
            ]
        )
        session.commit()

    try:
        response = client.get("/api/news/runtime")

        assert response.status_code == 200
        payload = response.json()
        assert payload["feed_status"] == "degraded"
        assert payload["last_incremental_event_at"] == "2026-03-25T02:38:30Z"
        assert payload["degraded_market_count"] == 2
        assert payload["markets"] == [
            {
                "market": "cn",
                "status": "offline",
                "mode": "none",
                "last_primary_success_at": "2026-03-25T01:40:00Z",
                "last_news_created_at": None,
                "degraded_reason": "no source succeeded within 30 minutes",
            },
            {
                "market": "hk",
                "status": "degraded",
                "mode": "secondary",
                "last_primary_success_at": "2026-03-25T01:50:00Z",
                "last_news_created_at": "2026-03-25T02:38:00Z",
                "degraded_reason": "primary sources failing; fallback supply active",
            },
            {
                "market": "us",
                "status": "delayed",
                "mode": "primary",
                "last_primary_success_at": "2026-03-25T02:20:00Z",
                "last_news_created_at": "2026-03-25T01:59:00Z",
                "degraded_reason": None,
            },
        ]
        assert payload["sources"] == [
            {
                "source_name": "CN Primary",
                "market": "cn",
                "tier": "primary",
                "status": "offline",
                "last_attempt_at": "2026-03-25T02:39:00Z",
                "last_success_at": "2026-03-25T01:40:00Z",
                "consecutive_failures": 4,
                "avg_fetch_latency_ms": 610.0,
                "latest_news_published_at": None,
                "latest_news_fetched_at": None,
                "last_error": None,
            },
            {
                "source_name": "HK Primary",
                "market": "hk",
                "tier": "primary",
                "status": "degraded",
                "last_attempt_at": "2026-03-25T02:35:00Z",
                "last_success_at": "2026-03-25T01:50:00Z",
                "consecutive_failures": 2,
                "avg_fetch_latency_ms": 500.0,
                "latest_news_published_at": None,
                "latest_news_fetched_at": None,
                "last_error": None,
            },
            {
                "source_name": "HK Secondary",
                "market": "hk",
                "tier": "secondary",
                "status": "ok",
                "last_attempt_at": "2026-03-25T02:38:00Z",
                "last_success_at": "2026-03-25T02:38:00Z",
                "consecutive_failures": 0,
                "avg_fetch_latency_ms": 260.0,
                "latest_news_published_at": "2026-03-25T02:35:00Z",
                "latest_news_fetched_at": "2026-03-25T02:38:00Z",
                "last_error": None,
            },
            {
                "source_name": "US Primary",
                "market": "us",
                "tier": "primary",
                "status": "delayed",
                "last_attempt_at": "2026-03-25T02:20:00Z",
                "last_success_at": "2026-03-25T02:20:00Z",
                "consecutive_failures": 0,
                "avg_fetch_latency_ms": 210.0,
                "latest_news_published_at": "2026-03-25T01:55:00Z",
                "latest_news_fetched_at": "2026-03-25T01:59:00Z",
                "last_error": None,
            },
        ]
    finally:
        with SessionLocal() as session:
            session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
            session.commit()


def test_news_list_applies_filters_and_limit() -> None:
    client = TestClient(app)

    response = client.get("/api/news", params={"market": "hk", "source_name": "Reuters", "limit": 1})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["market"] == "hk"
    assert payload["items"][0]["source_name"] == "Reuters"


def test_news_list_applies_keyword_filter() -> None:
    client = TestClient(app)

    response = client.get("/api/news", params={"q": "Tencent"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert "Tencent" in payload["items"][0]["title"]


def test_news_detail_serializes_utc_timestamps() -> None:
    client = TestClient(app)

    response = client.get("/api/news/1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["published_at"].endswith("Z")
    assert payload["fetched_at"].endswith("Z")
    assert payload["article"]["extracted_at"].endswith("Z")


def test_news_list_orders_by_published_at_before_fetched_at() -> None:
    client = TestClient(app)
    now = datetime.now(timezone.utc)
    url_hashes = [
        "test-order-published-newer",
        "test-order-fetched-newer",
    ]

    with SessionLocal() as session:
        session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
        session.add_all(
            [
                NewsItem(
                    source_name="Ordering Test",
                    source_url="https://example.com/ordering",
                    title="Published newer",
                    summary="newer publish time",
                    canonical_url="https://example.com/published-newer",
                    url_hash=url_hashes[0],
                    market="us",
                    language="en",
                    sentiment_label=None,
                    sentiment_score=None,
                    published_at=now - timedelta(minutes=2),
                    fetched_at=now - timedelta(minutes=30),
                    ingest_status="ingested",
                ),
                NewsItem(
                    source_name="Ordering Test",
                    source_url="https://example.com/ordering",
                    title="Fetched newer",
                    summary="newer fetch time",
                    canonical_url="https://example.com/fetched-newer",
                    url_hash=url_hashes[1],
                    market="us",
                    language="en",
                    sentiment_label=None,
                    sentiment_score=None,
                    published_at=now - timedelta(minutes=20),
                    fetched_at=now - timedelta(minutes=1),
                    ingest_status="ingested",
                ),
            ]
        )
        session.commit()

    try:
        response = client.get("/api/news", params={"source_name": "Ordering Test", "limit": 2})

        assert response.status_code == 200
        payload = response.json()
        assert [item["title"] for item in payload["items"]] == ["Published newer", "Fetched newer"]
    finally:
        with SessionLocal() as session:
            session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
            session.commit()


def test_news_list_keyset_pagination_returns_next_cursor() -> None:
    client = TestClient(app)
    now = datetime.now(timezone.utc)
    url_hashes = [
        "test-keyset-page-1",
        "test-keyset-page-2",
        "test-keyset-page-3",
    ]

    with SessionLocal() as session:
        session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
        session.add_all(
            [
                NewsItem(
                    source_name="Keyset Test",
                    source_url="https://example.com/keyset",
                    title="Newest item",
                    summary="page 1",
                    canonical_url="https://example.com/keyset-1",
                    url_hash=url_hashes[0],
                    market="us",
                    language="en",
                    sentiment_label=None,
                    sentiment_score=None,
                    published_at=now - timedelta(minutes=1),
                    fetched_at=now,
                    ingest_status="ingested",
                ),
                NewsItem(
                    source_name="Keyset Test",
                    source_url="https://example.com/keyset",
                    title="Middle item",
                    summary="page 2",
                    canonical_url="https://example.com/keyset-2",
                    url_hash=url_hashes[1],
                    market="us",
                    language="en",
                    sentiment_label=None,
                    sentiment_score=None,
                    published_at=now - timedelta(minutes=2),
                    fetched_at=now,
                    ingest_status="ingested",
                ),
                NewsItem(
                    source_name="Keyset Test",
                    source_url="https://example.com/keyset",
                    title="Oldest item",
                    summary="page 3",
                    canonical_url="https://example.com/keyset-3",
                    url_hash=url_hashes[2],
                    market="us",
                    language="en",
                    sentiment_label=None,
                    sentiment_score=None,
                    published_at=now - timedelta(minutes=3),
                    fetched_at=now,
                    ingest_status="ingested",
                ),
            ]
        )
        session.commit()

    try:
        first_page = client.get("/api/news", params={"source_name": "Keyset Test", "limit": 2})
        assert first_page.status_code == 200
        first_payload = first_page.json()
        assert [item["title"] for item in first_payload["items"]] == ["Newest item", "Middle item"]
        assert first_payload["next_cursor"]

        second_page = client.get(
            "/api/news",
            params={
                "source_name": "Keyset Test",
                "limit": 2,
                "cursor": first_payload["next_cursor"],
            },
        )
        assert second_page.status_code == 200
        second_payload = second_page.json()
        assert [item["title"] for item in second_payload["items"]] == ["Oldest item"]
        assert second_payload["next_cursor"] is None
    finally:
        with SessionLocal() as session:
            session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
            session.commit()


def test_news_feed_layout_returns_event_cards_topics_and_stream() -> None:
    client = TestClient(app)
    url_hashes = [
        "test-feed-layout-nvda-1",
        "test-feed-layout-nvda-2",
        "test-feed-layout-fed-1",
    ]
    topic_keys = ["test-feed-layout-ai", "test-feed-layout-macro"]
    watchlist_symbols = ["NVDA", "SMCI"]

    with SessionLocal() as session:
        session.execute(delete(WatchlistItem).where(WatchlistItem.symbol.in_(watchlist_symbols)))
        news_items = [
            NewsItem(
                source_name="Bloomberg",
                source_url="https://example.com/bloomberg",
                title="NVIDIA launches new AI chip platform",
                summary="Launch coverage highlights AI demand and supplier interest.",
                canonical_url="https://example.com/nvda-launch-1",
                url_hash=url_hashes[0],
                market="us",
                language="en",
                sentiment_label="positive",
                sentiment_score=0.72,
                    published_at=datetime(2099, 3, 28, 8, 0, tzinfo=timezone.utc),
                    fetched_at=datetime(2099, 3, 28, 8, 2, tzinfo=timezone.utc),
                ingest_status="ingested",
            ),
            NewsItem(
                source_name="Reuters",
                source_url="https://example.com/reuters",
                title="Suppliers rally after NVIDIA chip release",
                summary="Supply chain names rise after the new product cycle update.",
                canonical_url="https://example.com/nvda-launch-2",
                url_hash=url_hashes[1],
                market="us",
                language="en",
                sentiment_label="positive",
                sentiment_score=0.51,
                    published_at=datetime(2099, 3, 28, 7, 30, tzinfo=timezone.utc),
                    fetched_at=datetime(2099, 3, 28, 7, 35, tzinfo=timezone.utc),
                ingest_status="ingested",
            ),
            NewsItem(
                source_name="WSJ",
                source_url="https://example.com/wsj",
                title="Fed officials signal policy remains unchanged",
                summary="Macro tone stays cautious ahead of inflation data.",
                canonical_url="https://example.com/fed-policy-1",
                url_hash=url_hashes[2],
                market="us",
                language="en",
                sentiment_label="neutral",
                sentiment_score=0.02,
                    published_at=datetime(2099, 3, 28, 6, 45, tzinfo=timezone.utc),
                    fetched_at=datetime(2099, 3, 28, 6, 50, tzinfo=timezone.utc),
                ingest_status="ingested",
            ),
        ]
        session.add_all(news_items)
        session.flush()

        topics = [
                TopicCluster(
                    topic_key=topic_keys[0],
                    topic_title="AI Chip Launch",
                    topic_summary="NVIDIA's new product cycle is pulling suppliers and AI infrastructure names higher.",
                    keywords="nvidia,chip,launch,ai,supplier",
                    sentiment_score=0.64,
                    importance_score=9.91,
                    last_seen_at=datetime(2099, 3, 28, 8, 2, tzinfo=timezone.utc),
                ),
                TopicCluster(
                    topic_key=topic_keys[1],
                    topic_title="Fed Policy Watch",
                    topic_summary="Markets are waiting for the next inflation and rate signal.",
                    keywords="fed,policy,rate,inflation",
                    sentiment_score=0.0,
                    importance_score=9.61,
                    last_seen_at=datetime(2099, 3, 28, 6, 50, tzinfo=timezone.utc),
                ),
        ]
        session.add_all(topics)
        session.flush()

        session.add_all(
            [
                TopicNewsLink(topic_cluster_id=topics[0].id, news_id=news_items[0].id),
                TopicNewsLink(topic_cluster_id=topics[0].id, news_id=news_items[1].id),
                TopicNewsLink(topic_cluster_id=topics[1].id, news_id=news_items[2].id),
            ]
        )
        session.add_all(
            [
                NewsStockMention(news_id=news_items[0].id, symbol="NVDA", market="us", mention_type="body", confidence=0.92),
                NewsStockMention(news_id=news_items[0].id, symbol="SMCI", market="us", mention_type="body", confidence=0.75),
                NewsStockMention(news_id=news_items[1].id, symbol="NVDA", market="us", mention_type="body", confidence=0.81),
                WatchlistItem(symbol="NVDA", market="us", display_name="NVIDIA"),
                WatchlistItem(symbol="SMCI", market="us", display_name="Super Micro"),
            ]
        )
        session.commit()

    try:
        response = client.get("/api/news/feed-layout")

        assert response.status_code == 200
        payload = response.json()
        assert list(payload.keys()) == ["events", "topics", "stream"]
        assert payload["events"][0]["event_title"] == "AI Chip Launch"
        assert payload["events"][0]["event_type"] == "product"
        assert payload["events"][0]["primary_symbol"] == "NVDA"
        assert payload["events"][0]["related_symbols"] == ["NVDA", "SMCI"]
        assert payload["events"][0]["watchlist_hits"] == ["NVIDIA", "Super Micro"]
        assert payload["events"][0]["news_count"] == 2
        assert len(payload["events"][0]["news_items"]) == 2
        assert payload["topics"][0]["topic_title"] == "AI Chip Launch"
        stream_titles = {item["title"] for item in payload["stream"]}
        assert "NVIDIA launches new AI chip platform" in stream_titles
    finally:
        with SessionLocal() as session:
            news_ids = list(session.scalars(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
            topic_ids = list(session.scalars(select(TopicCluster.id).where(TopicCluster.topic_key.in_(topic_keys))))
            if news_ids:
                session.execute(delete(NewsStockMention).where(NewsStockMention.news_id.in_(news_ids)))
                session.execute(delete(TopicNewsLink).where(TopicNewsLink.news_id.in_(news_ids)))
                session.execute(delete(NewsItem).where(NewsItem.id.in_(news_ids)))
            if topic_ids:
                session.execute(delete(TopicCluster).where(TopicCluster.id.in_(topic_ids)))
            session.execute(delete(WatchlistItem).where(WatchlistItem.symbol.in_(watchlist_symbols)))
            session.commit()


def test_news_feed_layout_market_filter_keeps_related_symbols_in_market_scope() -> None:
    client = TestClient(app)
    url_hashes = [
        "test-feed-layout-market-us",
        "test-feed-layout-market-hk",
    ]
    topic_key = "test-feed-layout-cross-market"

    # Initial cleanup to remove potential leftovers from previous failed runs
    with SessionLocal() as session:
        news_ids = list(session.scalars(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
        topic_ids = list(session.scalars(select(TopicCluster.id).where(TopicCluster.topic_key == topic_key)))
        if news_ids:
            session.execute(delete(NewsStockMention).where(NewsStockMention.news_id.in_(news_ids)))
            session.execute(delete(TopicNewsLink).where(TopicNewsLink.news_id.in_(news_ids)))
            session.execute(delete(NewsItem).where(NewsItem.id.in_(news_ids)))
        if topic_ids:
            session.execute(delete(TopicCluster).where(TopicCluster.id.in_(topic_ids)))
        session.commit()

    with SessionLocal() as session:
        news_items = [
            NewsItem(
                source_name="Reuters",
                source_url="https://example.com/reuters",
                title="Apple supplier flags softer demand",
                summary="US supply chain warning.",
                canonical_url="https://example.com/apple-demand",
                url_hash=url_hashes[0],
                market="us",
                language="en",
                sentiment_label="negative",
                sentiment_score=-0.4,
                published_at=datetime(2026, 3, 28, 9, 0, tzinfo=timezone.utc),
                fetched_at=datetime(2026, 3, 28, 9, 1, tzinfo=timezone.utc),
                ingest_status="ingested",
            ),
            NewsItem(
                source_name="AAStocks",
                source_url="https://example.com/aastocks",
                title="Tencent AI product update",
                summary="Hong Kong internet update.",
                canonical_url="https://example.com/tencent-ai",
                url_hash=url_hashes[1],
                market="hk",
                language="en",
                sentiment_label="positive",
                sentiment_score=0.5,
                published_at=datetime(2026, 3, 28, 8, 55, tzinfo=timezone.utc),
                fetched_at=datetime(2026, 3, 28, 8, 56, tzinfo=timezone.utc),
                ingest_status="ingested",
            ),
        ]
        session.add_all(news_items)
        session.flush()

        topic = TopicCluster(
            topic_key=topic_key,
            topic_title="Cross Market Supply Chain",
            topic_summary="A topic carrying both US and HK mentions for filtering validation.",
            keywords="supplier,demand,ai",
            sentiment_score=0.0,
            importance_score=9.2,
            last_seen_at=datetime(2026, 3, 28, 9, 1, tzinfo=timezone.utc),
        )
        session.add(topic)
        session.flush()
        session.add_all(
            [
                TopicNewsLink(topic_cluster_id=topic.id, news_id=news_items[0].id),
                TopicNewsLink(topic_cluster_id=topic.id, news_id=news_items[1].id),
                NewsStockMention(news_id=news_items[0].id, symbol="AAPL", market="us", mention_type="body", confidence=0.9),
                NewsStockMention(news_id=news_items[1].id, symbol="0700.HK", market="hk", mention_type="body", confidence=0.9),
            ]
        )
        session.commit()

    try:
        response = client.get("/api/news/feed-layout", params={"market": "us"})

        assert response.status_code == 200
        payload = response.json()
        target_event = next(
            (e for e in payload["events"] if e["event_title"] == "Cross Market Supply Chain"),
            None
        )
        assert target_event is not None, f"Event not found in payload: {payload['events']}"
        assert target_event["market"] == "us"
        assert target_event["primary_symbol"] == "AAPL"
        assert target_event["related_symbols"] == ["AAPL"]
    finally:
        with SessionLocal() as session:
            news_ids = list(session.scalars(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
            topic_ids = list(session.scalars(select(TopicCluster.id).where(TopicCluster.topic_key == topic_key)))
            if news_ids:
                session.execute(delete(NewsStockMention).where(NewsStockMention.news_id.in_(news_ids)))
                session.execute(delete(TopicNewsLink).where(TopicNewsLink.news_id.in_(news_ids)))
                session.execute(delete(NewsItem).where(NewsItem.id.in_(news_ids)))
            if topic_ids:
                session.execute(delete(TopicCluster).where(TopicCluster.id.in_(topic_ids)))
            session.commit()


def test_news_event_detail_returns_reconstructed_topic_event() -> None:
    client = TestClient(app)
    url_hashes = [
        "test-event-detail-nvda-1",
        "test-event-detail-nvda-2",
    ]
    topic_key = "test-event-detail-ai"
    topic_id: int | None = None

    with SessionLocal() as session:
        news_items = [
            NewsItem(
                source_name="Reuters",
                source_url="https://example.com/reuters",
                title="NVIDIA launches new AI chip platform",
                summary="Launch headline.",
                canonical_url="https://example.com/nvda-launch",
                url_hash=url_hashes[0],
                market="us",
                language="en",
                sentiment_label="positive",
                sentiment_score=0.7,
                published_at=datetime(2026, 3, 28, 8, 0, tzinfo=timezone.utc),
                fetched_at=datetime(2026, 3, 28, 8, 5, tzinfo=timezone.utc),
                ingest_status="ingested",
            ),
            NewsItem(
                source_name="Bloomberg",
                source_url="https://example.com/bloomberg",
                title="Suppliers rally after NVIDIA chip release",
                summary="Supplier reaction.",
                canonical_url="https://example.com/nvda-supplier",
                url_hash=url_hashes[1],
                market="us",
                language="en",
                sentiment_label="positive",
                sentiment_score=0.5,
                published_at=datetime(2026, 3, 28, 7, 45, tzinfo=timezone.utc),
                fetched_at=datetime(2026, 3, 28, 7, 50, tzinfo=timezone.utc),
                ingest_status="ingested",
            ),
        ]
        session.add_all(news_items)
        session.flush()

        topic = TopicCluster(
            topic_key=topic_key,
            topic_title="AI Chip Launch",
            topic_summary="NVIDIA's new product cycle is pulling suppliers higher.",
            keywords="nvidia,chip,launch,ai,supplier",
            sentiment_score=0.64,
            importance_score=9.91,
            last_seen_at=datetime(2026, 3, 28, 8, 2, tzinfo=timezone.utc),
        )
        session.add(topic)
        session.flush()
        topic_id = topic.id
        session.add_all(
            [
                TopicNewsLink(topic_cluster_id=topic.id, news_id=news_items[0].id),
                TopicNewsLink(topic_cluster_id=topic.id, news_id=news_items[1].id),
                NewsStockMention(news_id=news_items[0].id, symbol="NVDA", market="us", mention_type="body", confidence=0.92),
                NewsStockMention(news_id=news_items[0].id, symbol="SMCI", market="us", mention_type="body", confidence=0.75),
                NewsStockMention(news_id=news_items[1].id, symbol="NVDA", market="us", mention_type="body", confidence=0.81),
            ]
        )
        session.commit()

    try:
        assert topic_id is not None
        response = client.get(f"/api/news/events/topic-{topic_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["event_key"] == f"topic-{topic_id}"
        assert payload["event_title"] == "AI Chip Launch"
        assert payload["primary_symbol"] == "NVDA"
        assert payload["related_symbols"] == ["NVDA", "SMCI"]
        assert payload["news_count"] == 2
        assert len(payload["news_items"]) == 2
        assert payload["news_items"][0]["title"] == "NVIDIA launches new AI chip platform"
    finally:
        with SessionLocal() as session:
            news_ids = list(session.scalars(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
            topic_ids = list(session.scalars(select(TopicCluster.id).where(TopicCluster.topic_key == topic_key)))
            if news_ids:
                session.execute(delete(NewsStockMention).where(NewsStockMention.news_id.in_(news_ids)))
                session.execute(delete(TopicNewsLink).where(TopicNewsLink.news_id.in_(news_ids)))
                session.execute(delete(NewsItem).where(NewsItem.id.in_(news_ids)))
            if topic_ids:
                session.execute(delete(TopicCluster).where(TopicCluster.id.in_(topic_ids)))
            session.commit()


def test_news_event_detail_returns_404_for_unknown_event_key() -> None:
    client = TestClient(app)

    response = client.get("/api/news/events/topic-999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "event not found"}
