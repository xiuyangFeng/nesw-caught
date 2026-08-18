"""K 线解析不再强制要求标的在自选股内。

交易台(/desk)选出的候选大多不在用户自选股里,个股研究页的 K 线此前会 404。
自选股命中时沿用其 symbol/market 口径;未命中时按代码本身推断市场
(normalize_symbol 对 A股/港股有确定后缀规则);推断不了才 404。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.market_chart_service import MarketChartService


def _fake_payload(symbol: str, market: str, interval: str, range_name: str, session) -> dict:
    return {
        "symbol": symbol,
        "interval": interval,
        "range": range_name,
        "stale": False,
        "candles": [],
        "indicators": {},
        "news_events": [],
        "_market": market,
    }


def test_kline_resolves_non_watchlist_a_share_by_symbol_inference() -> None:
    service = MarketChartService()
    with (
        patch("app.services.market_chart_service.WatchlistRepository") as repo_cls,
        patch.object(service, "_build_kline_payload", side_effect=_fake_payload),
    ):
        repo_cls.return_value.get_by_symbol.return_value = None
        payload = service.get_kline("000034.SZ", "1d", "1y", session=MagicMock())
    assert payload["symbol"] == "000034.SZ"
    assert payload["_market"] == "cn"


def test_kline_prefers_watchlist_market_when_symbol_is_watched() -> None:
    service = MarketChartService()
    watched = MagicMock()
    watched.symbol = "600519.SH"
    watched.market = "cn"
    with (
        patch("app.services.market_chart_service.WatchlistRepository") as repo_cls,
        patch.object(service, "_build_kline_payload", side_effect=_fake_payload),
    ):
        repo_cls.return_value.get_by_symbol.return_value = watched
        payload = service.get_kline("600519.SH", "1d", "1y", session=MagicMock())
    assert payload["symbol"] == "600519.SH"
    assert payload["_market"] == "cn"


def test_kline_still_404_for_unresolvable_symbol() -> None:
    service = MarketChartService()
    with patch("app.services.market_chart_service.WatchlistRepository") as repo_cls:
        repo_cls.return_value.get_by_symbol.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            service.get_kline("!!bogus!!", "1d", "1y", session=MagicMock())
    assert exc_info.value.status_code == 404
