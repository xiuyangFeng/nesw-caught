from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.news_item import NewsItem
from app.main import app


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
