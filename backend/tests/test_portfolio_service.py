"""持仓/组合视图服务测试。

覆盖：盈亏计算、按仓位价值加权的新闻排序、缺行情/缺持仓的优雅降级。
沿用 test_watchlist_research.py 的 fixture 风格：直接对共享测试库读写，
用唯一 symbol 前缀 + 逐用例清理，避免相互污染。
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.services.portfolio_service import PortfolioService


def _seed_news(
    session,
    *,
    title: str,
    symbol: str,
    market: str,
    sentiment_score: float | None,
    published_hours_ago: int = 6,
) -> NewsItem:
    url = f"https://example.com/portfolio/{uuid.uuid4().hex[:16]}"
    news = NewsItem(
        source_name="test",
        source_url=url,
        title=title,
        summary="portfolio test news",
        canonical_url=url,
        url_hash=sha256(url.encode()).hexdigest(),
        market=market,
        language="en",
        sentiment_label="neutral",
        sentiment_score=sentiment_score,
        published_at=datetime.now(timezone.utc) - timedelta(hours=published_hours_ago),
        fetched_at=datetime.now(timezone.utc),
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


def _ensure_holding(
    session,
    *,
    symbol: str,
    market: str,
    display_name: str,
    position_size: float | None,
    average_cost: float | None,
) -> None:
    item = session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
    if item is None:
        item = WatchlistItem(
            symbol=symbol,
            market=market,
            display_name=display_name,
            is_active=True,
            alert_threshold=None,
            alert_mode="fixed",
        )
        session.add(item)
    item.position_size = position_size
    item.average_cost = average_cost
    session.flush()


def _save_snapshot(session, *, symbol: str, market: str, price: float, change_percent: float = 0.0) -> None:
    session.add(
        PriceSnapshot(
            symbol=symbol,
            market=market,
            price=price,
            change_amount=change_percent,
            change_percent=change_percent,
            open_price=price,
            previous_close=price,
            day_high=price,
            day_low=price,
            volume=10000,
            provider_name="test_provider",
            provider_symbol=symbol,
            quote_status="ok",
            status_message=None,
            fetched_at=datetime.now(timezone.utc),
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
        for mention in session.scalars(select(NewsStockMention).where(NewsStockMention.news_id == news.id)):
            session.delete(mention)
        session.delete(news)
    for snapshot in session.scalars(select(PriceSnapshot).where(PriceSnapshot.symbol == symbol)):
        session.delete(snapshot)
    item = session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
    if item is not None:
        session.delete(item)


def _positions_by_symbol(summary) -> dict[str, object]:
    return {p.symbol: p for p in summary.positions}


def test_portfolio_summary_computes_pnl_and_weights() -> None:
    service = PortfolioService()
    symbols = ["PFAAA", "PFBBB", "PFCCC"]

    with SessionLocal() as session:
        for sym in symbols:
            _cleanup_symbol_data(session, sym)
        # 两只持仓 + 一只“仅关注、无持仓”的 PFCCC
        _ensure_holding(session, symbol="PFAAA", market="us", display_name="Alpha", position_size=10, average_cost=100)
        _save_snapshot(session, symbol="PFAAA", market="us", price=120)
        _ensure_holding(session, symbol="PFBBB", market="us", display_name="Beta", position_size=5, average_cost=200)
        _save_snapshot(session, symbol="PFBBB", market="us", price=180)
        _ensure_holding(session, symbol="PFCCC", market="us", display_name="Gamma", position_size=None, average_cost=None)
        session.commit()

        summary = service.build_summary(session)

        positions = _positions_by_symbol(summary)
        # 无持仓的 PFCCC 不进入组合
        assert "PFCCC" not in positions
        assert summary.position_count == 2
        assert summary.priced_position_count == 2

        alpha = positions["PFAAA"]
        assert alpha.market_value == 1200
        assert alpha.cost_basis == 1000
        assert alpha.unrealized_pnl == 200
        assert alpha.unrealized_pnl_percent == 20

        beta = positions["PFBBB"]
        assert beta.market_value == 900
        assert beta.unrealized_pnl == -100
        assert beta.unrealized_pnl_percent == -10

        assert summary.total_market_value == 2100
        assert summary.total_cost_basis == 2000
        assert summary.total_unrealized_pnl == 100
        assert summary.total_unrealized_pnl_percent == 5

        # 权重按市值：Alpha 1200/2100, Beta 900/2100
        assert abs(alpha.weight - 1200 / 2100) < 1e-6
        assert abs(beta.weight - 900 / 2100) < 1e-6

        for sym in symbols:
            _cleanup_symbol_data(session, sym)
        session.commit()


def test_portfolio_weighted_news_ranks_by_position_value() -> None:
    service = PortfolioService()
    symbols = ["PFHVY", "PFLGT"]

    with SessionLocal() as session:
        for sym in symbols:
            _cleanup_symbol_data(session, sym)
        # 重仓 PFHVY（市值 1000）vs 轻仓 PFLGT（市值 10）
        _ensure_holding(session, symbol="PFHVY", market="us", display_name="Heavy", position_size=100, average_cost=10)
        _save_snapshot(session, symbol="PFHVY", market="us", price=10)
        _ensure_holding(session, symbol="PFLGT", market="us", display_name="Light", position_size=1, average_cost=10)
        _save_snapshot(session, symbol="PFLGT", market="us", price=10)

        # 轻仓命中一条强情绪新闻；重仓命中一条弱情绪新闻。
        # 加权后重仓新闻应排在前（仓位价值主导）。
        _seed_news(session, title="Light strong", symbol="PFLGT", market="us", sentiment_score=0.9)
        _seed_news(session, title="Heavy mild", symbol="PFHVY", market="us", sentiment_score=0.3)
        # 无情绪分的新闻不应计入加权排序
        _seed_news(session, title="Heavy no sentiment", symbol="PFHVY", market="us", sentiment_score=None)
        session.commit()

        summary = service.build_summary(session)

        titles = [n.news_item.title for n in summary.weighted_news]
        assert "Heavy no sentiment" not in titles
        assert titles[0] == "Heavy mild"
        assert summary.weighted_news[0].symbols == ["PFHVY"]
        assert summary.weighted_news[0].impact_score >= summary.weighted_news[1].impact_score

        for sym in symbols:
            _cleanup_symbol_data(session, sym)
        session.commit()


def test_portfolio_degrades_without_quote() -> None:
    service = PortfolioService()
    symbol = "PFNOQ"

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        # 有持仓与成本，但没有任何行情快照
        _ensure_holding(session, symbol=symbol, market="us", display_name="NoQuote", position_size=10, average_cost=50)
        _seed_news(session, title="NoQuote catalyst", symbol=symbol, market="us", sentiment_score=0.8)
        session.commit()

        summary = service.build_summary(session)

        positions = _positions_by_symbol(summary)
        assert symbol in positions
        pos = positions[symbol]
        # 缺行情：市值/盈亏为空，状态非 ok，成本仍可算
        assert pos.current_price is None
        assert pos.market_value is None
        assert pos.unrealized_pnl is None
        assert pos.price_status != "ok"
        assert pos.cost_basis == 500
        assert summary.priced_position_count == 0
        assert summary.total_market_value == 0
        assert summary.total_unrealized_pnl == 0
        assert summary.total_unrealized_pnl_percent is None
        # 缺行情时按成本权重仍能给出加权新闻
        titles = [n.news_item.title for n in summary.weighted_news]
        assert "NoQuote catalyst" in titles

        _cleanup_symbol_data(session, symbol)
        session.commit()


def test_portfolio_excludes_items_without_position() -> None:
    service = PortfolioService()
    symbol = "PFWATCHONLY"

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        # 仅关注、无持仓：不应出现在组合中
        _ensure_holding(session, symbol=symbol, market="us", display_name="WatchOnly", position_size=None, average_cost=None)
        session.commit()

        summary = service.build_summary(session)

        assert symbol not in _positions_by_symbol(summary)

        _cleanup_symbol_data(session, symbol)
        session.commit()


def test_watchlist_patch_sets_position_then_portfolio_route_returns_pnl() -> None:
    client = TestClient(app)
    symbol = "PFROUTE"

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        _ensure_holding(session, symbol=symbol, market="us", display_name="RouteCo", position_size=None, average_cost=None)
        _save_snapshot(session, symbol=symbol, market="us", price=50.0)
        session.commit()

    # PATCH 写入持仓量与成本
    resp = client.patch(f"/api/watchlist/{symbol}", json={"position_size": 4, "average_cost": 40})
    assert resp.status_code == 200
    body = resp.json()
    assert body["position_size"] == 4
    assert body["average_cost"] == 40

    # GET /api/portfolio 汇总盈亏
    summary_resp = client.get("/api/portfolio")
    assert summary_resp.status_code == 200
    data = summary_resp.json()
    pos = next(p for p in data["positions"] if p["symbol"] == symbol)
    assert pos["market_value"] == 200  # 4 * 50
    assert pos["cost_basis"] == 160  # 4 * 40
    assert pos["unrealized_pnl"] == 40
    assert pos["unrealized_pnl_percent"] == 25

    # 部分更新：仅清空持仓量，成本保持不变（exclude_unset）
    clear_resp = client.patch(f"/api/watchlist/{symbol}", json={"position_size": None})
    assert clear_resp.status_code == 200
    cleared = clear_resp.json()
    assert cleared["position_size"] is None
    assert cleared["average_cost"] == 40

    with SessionLocal() as session:
        _cleanup_symbol_data(session, symbol)
        session.commit()


def test_watchlist_patch_returns_404_for_unknown_symbol() -> None:
    client = TestClient(app)
    resp = client.patch("/api/watchlist/PFNONEXISTENT", json={"position_size": 1})
    assert resp.status_code == 404
