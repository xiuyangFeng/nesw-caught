"""个股 AI 综合研判（stock_research_synthesis）测试。

覆盖：
- LLM 未配置时降级为规则要点汇总（并断言绝不联网）；
- LLM 可用时返回结构化研报（评级 / 催化剂 / 风险 / 关键时间线）；
- embedding 检索排序取 top-K 且顺序正确；
- LLM 调用失败时优雅降级、记录 llm_error 且不抛异常；
- 路由 GET /api/research/stock/{symbol} 端到端返回研报。

所有 LLM / 网络调用一律 mock，测试绝不真调外部服务。
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.schemas.stock_research import StockResearchReport
from app.services.llm_providers import CompletionResult
from app.services.stock_research_synthesis import synthesize_stock_research


def _seed_news(
    session,
    *,
    title: str,
    summary: str,
    symbol: str,
    market: str,
    sentiment_label: str = "neutral",
    published_hours_ago: int = 6,
    body: str | None = None,
) -> NewsItem:
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
        sentiment_label=sentiment_label,
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
    if body is not None:
        session.add(
            ArticleContent(
                news_id=news.id,
                content_text=body,
                extract_status="success",
                extracted_at=datetime.now(UTC),
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


def _save_snapshot(session, *, symbol: str, market: str, price: float, change_percent: float, hours_ago: int = 0) -> None:
    session.add(
        PriceSnapshot(
            symbol=symbol,
            market=market,
            price=price,
            change_amount=change_percent,
            change_percent=change_percent,
            open_price=price - 1,
            previous_close=price - 2,
            day_high=price + 1,
            day_low=price - 2,
            volume=10000,
            provider_name="test_provider",
            provider_symbol=symbol,
            quote_status="ok",
            status_message=None,
            fetched_at=datetime.now(UTC) - timedelta(hours=hours_ago),
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
        # between these models, so the unit-of-work has no dependency edge
        # to order the DELETEs across mappers. Without this flush,
        # "DELETE FROM news_item" can be emitted first, the DB cascade
        # removes the child rows, and the explicit DELETEs queued above then
        # match 0 rows (SAWarning).
        session.flush()
        session.delete(news)
    for snapshot in session.scalars(select(PriceSnapshot).where(PriceSnapshot.symbol == symbol)):
        session.delete(snapshot)
    item = session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
    if item is not None:
        session.delete(item)


def _fake_llm_config() -> MagicMock:
    fake_config = MagicMock()
    fake_config.id = 999
    fake_config.provider_name = "openai_compatible"
    fake_config.model_name = "deepseek-chat"
    fake_config.base_url = "https://example-llm.test/v1"
    fake_config.decrypted_api_key = "sk-live-test-key"
    return fake_config


def _boom_llm_client(*args, **kwargs):
    raise AssertionError("测试期间绝不允许发起真实 LLM/网络请求")


def test_synthesize_degrades_to_rule_mode_without_llm() -> None:
    """未配置 LLM 时降级为规则汇总，且不发起任何网络请求。"""
    symbol = "NVDA"
    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="NVIDIA")
        _save_snapshot(session, symbol=symbol, market="us", price=120.0, change_percent=2.5)
        _seed_news(
            session,
            title="NVIDIA wins major cloud order",
            summary="Large order boosts guidance.",
            symbol=symbol,
            market="us",
            sentiment_label="positive",
            published_hours_ago=4,
        )
        _seed_news(
            session,
            title="NVIDIA expands AI platform partnership",
            summary="New partnership drives growth.",
            symbol=symbol,
            market="us",
            sentiment_label="positive",
            published_hours_ago=10,
        )
        _seed_news(
            session,
            title="Export control policy pressures shipments",
            summary="Policy risk clouds outlook.",
            symbol=symbol,
            market="us",
            sentiment_label="negative",
            published_hours_ago=20,
        )
        session.commit()

    try:
        with patch(
            "app.repositories.llm_provider_config_repository.LLMProviderConfigRepository.get_default",
            return_value=None,
        ), patch("app.services.http_pool.get_llm_client", side_effect=_boom_llm_client):
            with SessionLocal() as session:
                report = synthesize_stock_research(symbol, session, lookback_days=7)

        assert isinstance(report, StockResearchReport)
        assert report.symbol == "NVDA"
        assert report.market == "us"
        assert report.mode == "rule"
        assert report.llm_error is None
        assert report.news_count == 3
        # 2 条 positive -> bull_case，1 条 negative -> bear_case，净分 +1 => bullish
        assert len(report.bull_case) == 2
        assert len(report.bear_case) == 1
        assert report.overall_rating == "bullish"
        assert len(report.key_events) == 3
        assert len(report.references) == 3
        assert report.price_context.price == 120.0
        assert report.price_context.snapshot_count == 1
    finally:
        with SessionLocal() as session:
            _cleanup_symbol_data(session, symbol)
            session.commit()


def test_synthesize_with_llm_returns_structured_report() -> None:
    """LLM 可用时返回结构化研报（评级/催化剂/风险/时间线）。"""
    symbol = "AAPL"
    llm_json = json.dumps(
        {
            "overall_rating": "bullish",
            "rating_rationale": "服务业务与新品周期共振。",
            "summary": "苹果近期新品与服务收入表现稳健，整体偏多。",
            "bull_case": ["新品备货超预期", "服务收入创新高"],
            "bear_case": ["监管反垄断风险"],
            "key_events": [
                {"date": "2026-07-10", "title": "新品发布会", "description": "iPhone 新机型", "impact": "positive"},
                {"date": "2026-07-11", "title": "反垄断调查", "description": "欧盟审查", "impact": "negative"},
            ],
        }
    )

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Apple")
        _save_snapshot(session, symbol=symbol, market="us", price=210.0, change_percent=1.2)
        _seed_news(
            session,
            title="Apple unveils new iPhone lineup",
            summary="Strong pre-orders reported.",
            symbol=symbol,
            market="us",
            sentiment_label="positive",
            published_hours_ago=5,
            body="Apple announced its new iPhone lineup with record pre-orders across regions.",
        )
        session.commit()

    try:
        with patch(
            "app.repositories.llm_provider_config_repository.LLMProviderConfigRepository.get_default",
            return_value=_fake_llm_config(),
        ), patch(
            "app.services.stock_research_synthesis.build_provider"
        ) as mock_build:
            mock_provider = MagicMock()
            mock_provider.complete.return_value = CompletionResult(content=llm_json)
            mock_build.return_value = mock_provider

            with SessionLocal() as session:
                report = synthesize_stock_research(symbol, session, lookback_days=7)

            # 只有一条新闻（<= top_k），不应触发 embedding 网络调用
            mock_provider.embed_texts.assert_not_called()
            mock_provider.complete.assert_called_once()

        assert report.mode == "llm"
        assert report.model_name == "deepseek-chat"
        assert report.overall_rating == "bullish"
        assert report.rating_rationale == "服务业务与新品周期共振。"
        assert report.bull_case == ["新品备货超预期", "服务收入创新高"]
        assert report.bear_case == ["监管反垄断风险"]
        assert len(report.key_events) == 2
        assert report.key_events[0].impact == "positive"
        assert report.key_events[1].impact == "negative"
        assert report.references[0].news_id > 0
        assert report.llm_error is None
    finally:
        with SessionLocal() as session:
            _cleanup_symbol_data(session, symbol)
            session.commit()


def test_synthesize_ranks_news_by_embedding_relevance() -> None:
    """候选新闻超过 top-K 时用 embedding 相似度排序，最相关者排前且截断到 top-K。"""
    symbol = "MSFT"
    relevant_marker = "RELEVANT-COPILOT"

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Microsoft")
        _save_snapshot(session, symbol=symbol, market="us", price=430.0, change_percent=0.5)
        # 播种 10 条新闻（> TOP_K_NEWS=8），其中一条被标记为最相关
        for i in range(9):
            _seed_news(
                session,
                title=f"Generic Microsoft update {i}",
                summary="routine news",
                symbol=symbol,
                market="us",
                published_hours_ago=i + 1,
            )
        _seed_news(
            session,
            title=f"{relevant_marker} drives new AI monetization",
            summary="highly relevant catalyst",
            symbol=symbol,
            market="us",
            published_hours_ago=50,
        )
        session.commit()

    def fake_embed_batch(texts: list[str]) -> list[list[float]]:
        # query 向量与 marker 新闻向量同向 -> 余弦相似度最高
        return [
            [1.0, 0.0] if (relevant_marker in text or "催化剂" in text) else [0.2, 1.0]
            for text in texts
        ]

    try:
        with patch(
            "app.repositories.llm_provider_config_repository.LLMProviderConfigRepository.get_default",
            return_value=_fake_llm_config(),
        ), patch(
            "app.services.stock_research_synthesis.build_provider"
        ) as mock_build:
            mock_provider = MagicMock()
            mock_provider.embed_texts.side_effect = fake_embed_batch
            mock_provider.complete.return_value = CompletionResult(content=json.dumps({"summary": "ok"}))
            mock_build.return_value = mock_provider

            with SessionLocal() as session:
                report = synthesize_stock_research(symbol, session, lookback_days=30)

            # 批量排序应恰好一次请求（query + 全部候选文档合并成一次 embed_texts 调用）。
            mock_provider.embed_texts.assert_called_once()
        # top-K 截断为 8 条，最相关的 marker 新闻排在首位
        assert len(report.references) == 8
        assert relevant_marker in report.references[0].title
    finally:
        with SessionLocal() as session:
            _cleanup_symbol_data(session, symbol)
            session.commit()


def test_synthesize_degrades_when_llm_call_raises() -> None:
    """LLM 调用抛异常时优雅降级为规则模式并记录 llm_error，绝不上抛。"""
    symbol = "TSLA"

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Tesla")
        _save_snapshot(session, symbol=symbol, market="us", price=250.0, change_percent=-1.0)
        _seed_news(
            session,
            title="Tesla faces production risk warning",
            summary="A negative development.",
            symbol=symbol,
            market="us",
            sentiment_label="negative",
            published_hours_ago=3,
        )
        session.commit()

    try:
        with patch(
            "app.repositories.llm_provider_config_repository.LLMProviderConfigRepository.get_default",
            return_value=_fake_llm_config(),
        ), patch(
            "app.services.stock_research_synthesis.build_provider"
        ) as mock_build:
            mock_provider = MagicMock()
            mock_provider.complete.side_effect = RuntimeError("llm provider request failed")
            mock_build.return_value = mock_provider

            with SessionLocal() as session:
                report = synthesize_stock_research(symbol, session, lookback_days=7)

        assert report.mode == "rule"
        assert report.llm_error is not None
        assert "llm provider request failed" in report.llm_error
        assert report.overall_rating in {"bearish", "strong_bearish", "neutral"}
        assert len(report.bear_case) == 1
    finally:
        with SessionLocal() as session:
            _cleanup_symbol_data(session, symbol)
            session.commit()


def test_synthesize_no_recent_news_returns_unknown() -> None:
    """窗口内无关联新闻时返回 unknown 评级，且不发起网络请求。"""
    symbol = "AMD"
    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="AMD")
        _save_snapshot(session, symbol=symbol, market="us", price=160.0, change_percent=0.3)
        session.commit()

    try:
        with patch(
            "app.repositories.llm_provider_config_repository.LLMProviderConfigRepository.get_default",
            return_value=_fake_llm_config(),
        ), patch("app.services.http_pool.get_llm_client", side_effect=_boom_llm_client):
            with SessionLocal() as session:
                report = synthesize_stock_research(symbol, session, lookback_days=7)

        assert report.news_count == 0
        assert report.references == []
        assert report.overall_rating == "unknown"
        assert report.mode == "rule"
    finally:
        with SessionLocal() as session:
            _cleanup_symbol_data(session, symbol)
            session.commit()


def test_stock_research_route_returns_report() -> None:
    """路由 GET /api/research/stock/{symbol} 端到端返回结构化研报。"""
    client = TestClient(app)
    symbol = "GOOG"
    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_watchlist_item(session, symbol=symbol, market="us", display_name="Alphabet")
        _save_snapshot(session, symbol=symbol, market="us", price=180.0, change_percent=1.1)
        _seed_news(
            session,
            title="Alphabet cloud revenue accelerates",
            summary="Cloud growth beats expectations.",
            symbol=symbol,
            market="us",
            sentiment_label="positive",
            published_hours_ago=6,
        )
        session.commit()

    try:
        with patch(
            "app.repositories.llm_provider_config_repository.LLMProviderConfigRepository.get_default",
            return_value=None,
        ):
            response = client.get("/api/research/stock/GOOG?lookback_days=7")

        assert response.status_code == 200
        payload = response.json()
        assert payload["symbol"] == "GOOG"
        assert payload["market"] == "us"
        assert payload["mode"] == "rule"
        assert payload["lookback_days"] == 7
        assert payload["news_count"] == 1
        assert "price_context" in payload
        assert payload["overall_rating"] == "bullish"
    finally:
        with SessionLocal() as session:
            _cleanup_symbol_data(session, symbol)
            session.commit()
