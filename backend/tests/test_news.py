from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.news_item import NewsItem
from app.models.source_health import SourceHealth
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
    assert len(payload) == 1
    assert payload[0]["market"] == "hk"
    assert payload[0]["source_name"] == "Reuters"


def test_news_list_applies_keyword_filter() -> None:
    client = TestClient(app)

    response = client.get("/api/news", params={"q": "Tencent"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert "Tencent" in payload[0]["title"]


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
        assert [item["title"] for item in payload] == ["Published newer", "Fetched newer"]
    finally:
        with SessionLocal() as session:
            session.execute(delete(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
            session.commit()
