import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem


def _seed_news(session, *, title: str, summary: str, symbol: str, market: str, published_hours_ago: int = 6) -> NewsItem:
    url = f"https://example.com/research/{uuid.uuid4().hex[:16]}"
    news = NewsItem(
        source_name="test",
        source_url=url,
        title=title,
        summary=summary,
        canonical_url=url,
        url_hash=sha256(url.encode()).hexdigest(),
        market=market,
        language="en",
        sentiment_label="neutral",
        sentiment_score=None,
        published_at=datetime.now(UTC) - timedelta(hours=published_hours_ago),
        fetched_at=datetime.now(UTC),
        ingest_status="ingested",
    )
    session.add(news)
    session.flush()
    session.add(
        NewsStockMention(
            news_id=news.id,
            symbol=symbol,
            market=market,
            mention_type="manual",
            confidence=0.9,
        )
    )
    session.flush()
    return news


def _ensure_watchlist_item(session, *, symbol: str, market: str, display_name: str) -> None:
    item = session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
    if item is None:
        session.add(
            WatchlistItem(
                symbol=symbol,
                market=market,
                display_name=display_name,
                is_active=True,
                alert_threshold=None,
                alert_mode="fixed",
            )
        )
        session.flush()


def _save_snapshot(session, *, symbol: str, market: str, provider_symbol: str, change_percent: float) -> None:
    session.add(
        PriceSnapshot(
            symbol=symbol,
            market=market,
            price=100.0,
            change_amount=change_percent,
            change_percent=change_percent,
            open_price=99.0,
            previous_close=98.0,
            day_high=101.0,
            day_low=97.0,
            volume=10000,
            provider_name="test_provider",
            provider_symbol=provider_symbol,
            quote_status="ok",
            status_message=None,
            fetched_at=datetime.now(UTC),
        )
    )
    session.flush()


def _cleanup_symbol_data(session, symbol: str) -> None:
    news_items = list(
        session.scalars(
            select(NewsItem)
            .join(NewsStockMention, NewsStockMention.news_id == NewsItem.id)
            .where(NewsStockMention.symbol == symbol)
        )
    )
    for news in news_items:
        for article in session.scalars(select(ArticleContent).where(ArticleContent.news_id == news.id)):
            session.delete(article)
        for mention in session.scalars(select(NewsStockMention).where(NewsStockMention.news_id == news.id)):
            session.delete(mention)
        # Flush the child-row deletes before deleting the parent NewsItem.
        # NewsStockMention/ArticleContent have a DB-level ON DELETE CASCADE
        # FK to news_item (SQLite has PRAGMA foreign_keys=ON), but this
        # codebase intentionally does not declare ORM relationship()s
        # between these models (explicit repository queries instead of ORM
        # cascade). Without a relationship(), SQLAlchemy's unit-of-work has
        # no dependency edge between the two mappers, so within a single
        # flush it does not guarantee child-before-parent DELETE ordering.
        # If DELETE FROM news_item were emitted first, the DB's own CASCADE
        # would remove the mention/article rows, and the explicit DELETE
        # statements queued above would then match 0 rows, triggering
        # "SAWarning: DELETE statement ... expected to delete 1 row(s); 0
        # were matched". Flushing here forces the child deletes to hit the
        # database before the parent delete is even queued, so ordering is
        # deterministic and no rows are cascade-deleted out from under us.
        session.flush()
        session.delete(news)
    for snapshot in session.scalars(select(PriceSnapshot).where(PriceSnapshot.symbol == symbol)):
        session.delete(snapshot)
    item = session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
    if item is not None:
        session.delete(item)


def test_watchlist_research_brief_groups_news_into_driver_categories() -> None:
    client = TestClient(app)

    with SessionLocal() as session:
        symbol = "NVDA"
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="NVIDIA")
        _save_snapshot(session, symbol=symbol, market="us", provider_symbol="NVDA", change_percent=1.8)
        _seed_news(
            session,
            title="US export control policy tightens AI chip shipments",
            summary="New policy guidance targets advanced AI accelerators.",
            symbol=symbol,
            market="us",
            published_hours_ago=4,
        )
        _seed_news(
            session,
            title="NVIDIA wins major cloud order for next-gen platform",
            summary="The company secured a large order and expanded capex plans.",
            symbol=symbol,
            market="us",
            published_hours_ago=8,
        )
        _seed_news(
            session,
            title="Upstream suppliers see demand rise across the AI supply chain",
            summary="Supply chain pricing and capacity remain tight.",
            symbol=symbol,
            market="us",
            published_hours_ago=18,
        )
        session.commit()

    response = client.get("/api/watchlist/NVDA/research-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "NVDA"
    assert payload["market"] == "us"
    assert payload["top_action_level"] == "act_now"
    categories = {driver["category"] for driver in payload["drivers"]}
    assert "policy_macro" in categories
    assert "company_action" in categories
    assert "supply_chain" in categories
    assert any(driver["action_level"] == "act_now" for driver in payload["drivers"])

    with SessionLocal() as session:
        _cleanup_symbol_data(session, "NVDA")
        session.commit()


def test_watchlist_research_brief_flags_unexplained_price_move_without_strong_drivers() -> None:
    client = TestClient(app)

    with SessionLocal() as session:
        symbol = "AAPL"
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Apple")
        _save_snapshot(session, symbol=symbol, market="us", provider_symbol="AAPL", change_percent=4.7)
        _seed_news(
            session,
            title="Apple shares jump as traders chase momentum",
            summary="The stock rallied sharply in active trading.",
            symbol=symbol,
            market="us",
            published_hours_ago=96,
        )
        session.commit()

    response = client.get("/api/watchlist/AAPL/research-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["has_unexplained_price_move"] is True
    assert payload["top_action_level"] == "watch_today"
    assert payload["drivers"][0]["category"] == "price_action"

    with SessionLocal() as session:
        _cleanup_symbol_data(session, "AAPL")
        session.commit()


def test_watchlist_research_brief_accepts_a_share_alias_lookup() -> None:
    client = TestClient(app)

    with SessionLocal() as session:
        symbol = "600519.SH"
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="cn", display_name="贵州茅台")
        _save_snapshot(session, symbol=symbol, market="cn", provider_symbol="600519.SS", change_percent=2.1)
        _seed_news(
            session,
            title="工信部新政策支持高端制造升级",
            summary="政策支持带动产业链预期升温。",
            symbol=symbol,
            market="cn",
            published_hours_ago=5,
        )
        session.commit()

    response = client.get("/api/watchlist/SH600519/research-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "600519.SH"
    assert payload["market"] == "cn"
    assert payload["drivers"][0]["category"] == "policy_macro"

    with SessionLocal() as session:
        _cleanup_symbol_data(session, "600519.SH")
        session.commit()


def test_watchlist_research_brief_returns_none_top_action_when_no_drivers_exist() -> None:
    client = TestClient(app)

    with SessionLocal() as session:
        symbol = "TSLA"
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Tesla")
        _save_snapshot(session, symbol=symbol, market="us", provider_symbol="TSLA", change_percent=5.1)
        session.commit()

    response = client.get("/api/watchlist/TSLA/research-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["drivers"] == []
    assert payload["has_unexplained_price_move"] is True
    assert payload["top_action_level"] == "none"

    with SessionLocal() as session:
        _cleanup_symbol_data(session, "TSLA")
        session.commit()


def test_watchlist_ai_insight_api() -> None:
    from unittest.mock import MagicMock, patch
    client = TestClient(app)

    with SessionLocal() as session:
        symbol = "MSFT"
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Microsoft")
        _seed_news(
            session,
            title="Microsoft releases new AI cloud integration tools",
            summary="New integrations showcase growth potential in SaaS markets.",
            symbol=symbol,
            market="us",
            published_hours_ago=2,
        )
        session.commit()

    with patch("app.repositories.llm_provider_config_repository.LLMProviderConfigRepository.get_default", return_value=None):
        res_no_llm = client.post("/api/watchlist/MSFT/ai-insight")
        assert res_no_llm.status_code == 400
        assert "llm provider is not configured" in res_no_llm.json()["detail"]

    fake_config = MagicMock()
    fake_config.id = 999
    fake_config.provider_name = "openai_compatible"
    fake_config.model_name = "deepseek-chat"
    fake_config.base_url = "https://example-llm.test/v1"
    fake_config.decrypted_api_key = "sk-live-test-key"

    with patch("app.repositories.llm_provider_config_repository.LLMProviderConfigRepository.get_default", return_value=fake_config), \
         patch("app.services.llm_providers.OpenAICompatibleProvider.generate_text") as mock_gen:

        mock_gen.return_value = "# AI Insight\nStrong growth potential."

        res = client.post("/api/watchlist/MSFT/ai-insight")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "MSFT"
        assert "# AI Insight" in data["insight_text"]
        assert "generated_at" in data

    with SessionLocal() as session:
        _cleanup_symbol_data(session, "MSFT")
        session.commit()
