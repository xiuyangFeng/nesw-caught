"""Tests for stock news auto-search when adding watchlist items."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.services.news_ingestion import SourceItem
from app.services.stock_news_search import StockNewsSearchService, _ExternalSearchWorker


def _seed_news_for_symbol(session, title: str, symbol_hint: str, market: str = "us") -> NewsItem:
    import uuid
    from hashlib import sha256

    now = datetime.now(timezone.utc)
    unique_id = uuid.uuid4().hex[:16]
    url = f"https://example.com/test/{unique_id}"
    url_hash = sha256(url.encode()).hexdigest()

    existing = session.scalar(select(NewsItem).where(NewsItem.url_hash == url_hash))
    if existing is not None:
        return existing

    news = NewsItem(
        source_name="test",
        source_url=url,
        title=title,
        summary=f"Summary about {symbol_hint}",
        canonical_url=url,
        url_hash=url_hash,
        market=market,
        language="en",
        sentiment_label=None,
        sentiment_score=None,
        published_at=now - timedelta(hours=1),
        fetched_at=now,
        ingest_status="ingested",
    )
    session.add(news)
    session.flush()
    return news


def _cleanup_news(session, news_id: int) -> None:
    for ac in session.scalars(select(ArticleContent).where(ArticleContent.news_id == news_id)):
        session.delete(ac)
    for m in session.scalars(select(NewsStockMention).where(NewsStockMention.news_id == news_id)):
        session.delete(m)
    news = session.scalar(select(NewsItem).where(NewsItem.id == news_id))
    if news:
        session.delete(news)


def test_sync_match_finds_existing_news_by_symbol():
    with SessionLocal() as session:
        news = _seed_news_for_symbol(session, "MSFT earnings beat expectations", "MSFT")
        session.commit()
        news_id = news.id

        service = StockNewsSearchService(session)
        count = service.sync_match_existing("MSFT", "Microsoft", "us")

        assert count >= 1
        mention = session.scalar(
            select(NewsStockMention).where(
                NewsStockMention.news_id == news_id,
                NewsStockMention.symbol == "MSFT",
            )
        )
        assert mention is not None
        assert mention.mention_type == "keyword_match"
        assert mention.confidence == 0.6

        _cleanup_news(session, news_id)
        session.commit()


def test_sync_match_finds_existing_news_by_display_name():
    with SessionLocal() as session:
        news = _seed_news_for_symbol(session, "Microsoft announces new AI features", "Microsoft")
        session.commit()
        news_id = news.id

        service = StockNewsSearchService(session)
        count = service.sync_match_existing("MSFT", "Microsoft", "us")

        assert count >= 1
        mention = session.scalar(
            select(NewsStockMention).where(
                NewsStockMention.news_id == news_id,
                NewsStockMention.symbol == "MSFT",
            )
        )
        assert mention is not None

        _cleanup_news(session, news_id)
        session.commit()


def test_sync_match_skips_duplicate_mentions():
    with SessionLocal() as session:
        news = _seed_news_for_symbol(session, "UNIQUEGOOG789 revenue growth accelerates", "UNIQUEGOOG789")
        session.add(
            NewsStockMention(
                news_id=news.id,
                symbol="UNIQUEGOOG789",
                market="us",
                mention_type="manual",
                confidence=0.9,
            )
        )
        session.commit()
        news_id = news.id

        service = StockNewsSearchService(session)
        count = service.sync_match_existing("UNIQUEGOOG789", "UNIQUEGOOG789", "us")

        assert count == 1

        mentions = list(
            session.scalars(
                select(NewsStockMention).where(
                    NewsStockMention.news_id == news_id,
                    NewsStockMention.symbol == "UNIQUEGOOG789",
                )
            )
        )
        assert len(mentions) == 1

        _cleanup_news(session, news_id)
        session.commit()


def test_sync_match_returns_zero_when_no_match():
    with SessionLocal() as session:
        service = StockNewsSearchService(session)
        count = service.sync_match_existing("ZZZZZ", "NoSuchCompany", "us")
        assert count == 0


def test_external_search_persists_tavily_results():
    fake_items = [
        SourceItem(
            title="Tesla launches new model",
            canonical_url="https://example.com/tesla-new-model-ext-test",
            summary="Tesla announced a new vehicle model today.",
            content_text="Tesla announced a new vehicle model today with improved range.",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
        ),
    ]

    with SessionLocal() as session:
        with patch(
            "app.services.stock_news_search._ExternalSearchWorker._search_tavily",
            return_value=fake_items,
        ), patch(
            "app.services.stock_news_search._ExternalSearchWorker._search_google_news",
            return_value=[],
        ), patch(
            "app.services.stock_news_search._ExternalSearchWorker._try_llm_expand",
            return_value=None,
        ):
            worker = _ExternalSearchWorker(session)
            count = worker.search_and_persist("TSLA", "Tesla", "us")

        assert count >= 1

        from hashlib import sha256

        url_hash = sha256("https://example.com/tesla-new-model-ext-test".encode()).hexdigest()
        news = session.scalar(select(NewsItem).where(NewsItem.url_hash == url_hash))
        assert news is not None
        assert news.source_name == "web_search"

        mention = session.scalar(
            select(NewsStockMention).where(
                NewsStockMention.news_id == news.id,
                NewsStockMention.symbol == "TSLA",
            )
        )
        assert mention is not None
        assert mention.mention_type == "search_result"

        _cleanup_news(session, news.id)
        session.commit()


def test_external_search_falls_back_to_google_news():
    google_items = [
        SourceItem(
            title="Amazon expands cloud services",
            canonical_url="https://example.com/amazon-cloud-ext-test",
            summary="Amazon Web Services introduces new features.",
            content_text=None,
            published_at=datetime.now(timezone.utc) - timedelta(hours=3),
        ),
    ]

    with SessionLocal() as session:
        with patch(
            "app.services.stock_news_search._ExternalSearchWorker._search_tavily",
            return_value=[],
        ), patch(
            "app.services.stock_news_search._ExternalSearchWorker._search_google_news",
            return_value=google_items,
        ), patch(
            "app.services.stock_news_search._ExternalSearchWorker._try_llm_expand",
            return_value=None,
        ):
            worker = _ExternalSearchWorker(session)
            count = worker.search_and_persist("AMZN", "Amazon", "us")

        assert count >= 1

        from hashlib import sha256

        url_hash = sha256("https://example.com/amazon-cloud-ext-test".encode()).hexdigest()
        news = session.scalar(select(NewsItem).where(NewsItem.url_hash == url_hash))
        assert news is not None

        mention = session.scalar(
            select(NewsStockMention).where(
                NewsStockMention.news_id == news.id,
                NewsStockMention.symbol == "AMZN",
            )
        )
        assert mention is not None

        _cleanup_news(session, news.id)
        session.commit()


def test_watchlist_create_triggers_sync_match():
    with SessionLocal() as session:
        news = _seed_news_for_symbol(session, "NVDA GPU demand remains strong in Q2", "NVDA")
        session.commit()
        news_id = news.id

    client = TestClient(app)

    with patch(
        "app.api.routes.watchlist.StockNewsSearchService.trigger_async_external_search"
    ) as mock_async:
        response = client.post(
            "/api/watchlist",
            json={
                "symbol": "NVDA",
                "market": "us",
                "display_name": "NVIDIA",
                "alert_threshold": 5.0,
                "alert_mode": "fixed",
            },
        )

    if response.status_code == 409:
        return

    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "NVDA"

    with SessionLocal() as session:
        mention = session.scalar(
            select(NewsStockMention).where(
                NewsStockMention.news_id == news_id,
                NewsStockMention.symbol == "NVDA",
            )
        )
        assert mention is not None

        for m in session.scalars(select(NewsStockMention).where(NewsStockMention.symbol == "NVDA")):
            session.delete(m)

        from app.models.watchlist_item import WatchlistItem

        wi = session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == "NVDA"))
        if wi:
            session.delete(wi)

        news_item = session.scalar(select(NewsItem).where(NewsItem.id == news_id))
        if news_item:
            session.delete(news_item)
        session.commit()
