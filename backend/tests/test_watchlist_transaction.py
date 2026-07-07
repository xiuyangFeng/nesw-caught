"""Watchlist 创建的事务边界回归测试。

Repository 层只 flush，提交权收口在请求级依赖 get_db_session：
- watchlist create + sync_match_existing 在同一事务内；
- 任一步失败时整体回滚，watchlist 表不能留下半提交残留。
"""

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.watchlist_item import WatchlistItem
from app.services.stock_news_search import StockNewsSearchService


def _delete_watchlist_symbol(symbol: str) -> None:
    with SessionLocal() as session:
        item = session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
        if item is not None:
            session.delete(item)
            session.commit()


def _load_watchlist_symbol(symbol: str) -> WatchlistItem | None:
    with SessionLocal() as session:
        return session.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol))


def test_watchlist_create_rolls_back_when_sync_match_fails() -> None:
    symbol = "ZZTXROLLBACK"
    _delete_watchlist_symbol(symbol)
    client = TestClient(app, raise_server_exceptions=False)

    try:
        with patch.object(
            StockNewsSearchService,
            "sync_match_existing",
            side_effect=RuntimeError("sync match blew up"),
        ):
            response = client.post(
                "/api/watchlist",
                json={"symbol": symbol, "market": "us", "display_name": "Rollback Probe"},
            )

        assert response.status_code == 500
        # 创建与 sync_match_existing 处于同一事务：sync 失败后整体回滚，不留残留。
        assert _load_watchlist_symbol(symbol) is None
    finally:
        _delete_watchlist_symbol(symbol)


def test_watchlist_create_commits_at_request_boundary() -> None:
    symbol = "ZZTXCOMMIT"
    _delete_watchlist_symbol(symbol)
    client = TestClient(app)

    try:
        # 返回足够大的匹配数，避免触发异步外部搜索的网络调用。
        with patch.object(StockNewsSearchService, "sync_match_existing", return_value=999):
            response = client.post(
                "/api/watchlist",
                json={"symbol": symbol, "market": "us", "display_name": "Commit Probe"},
            )

        assert response.status_code == 201
        # 请求成功结束后由 get_db_session 统一提交，新会话必须可见。
        persisted = _load_watchlist_symbol(symbol)
        assert persisted is not None
        assert persisted.display_name == "Commit Probe"
    finally:
        _delete_watchlist_symbol(symbol)
