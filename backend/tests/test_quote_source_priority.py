"""按市场选择行情主源的回归测试。

2026-07-27 实测（002384.SZ 东山精密，收盘后）：

- Yahoo 对 A 股**当日**日线的 ``Close`` 是 NaN（Open/High/Low/Volume 都有值），
  批量路径 ``dropna(subset=["Close"])`` 会把今天整行丢掉，回退成上一交易日的收盘
  数据，而 ``status`` 仍然是 ``ok`` —— 于是"Yahoo 失败才降级腾讯"的兜底永远不
  触发，页面上显示的是**整整一天前**的价格（199.18 而非真实的 211.90，漏掉
  +6.39% 的涨幅），且昨收/涨跌/振幅全为空。
- 同一时刻腾讯源字段完整且正确，港股两源一致，A 股的昨收只有腾讯是对的
  （688256.SH：腾讯 1225.0 = 上一交易日收盘，Yahoo 1216.0 错误）。
- 美股腾讯不支持，必须留在 Yahoo。

因此 cn/hk 以腾讯为主源、Yahoo 为降级；us 反之。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from app.db.session import SessionLocal
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.services.quote_provider import QuoteRecord
from app.services.quote_service import QuoteService

CN_SYMBOL = "002384.SZ"
US_SYMBOL = "AAPL"


def _record(symbol: str, market: str, price: float, source: str, *, status: str = "ok") -> QuoteRecord:
    return QuoteRecord(
        symbol=symbol,
        market=market,
        provider_symbol=symbol,
        price=price,
        change_amount=1.0,
        change_percent=0.5,
        open_price=price,
        previous_close=price - 1,
        day_high=price,
        day_low=price,
        volume=100,
        status=status,
        source=source,
        message=None if status == "ok" else "boom",
        fetched_at=datetime.now(UTC),
    )


def _reset(session) -> None:
    for symbol in (CN_SYMBOL, US_SYMBOL):
        session.query(PriceSnapshot).filter(PriceSnapshot.symbol == symbol).delete()
        item = session.query(WatchlistItem).filter(WatchlistItem.symbol == symbol).one_or_none()
        if item is not None:
            session.delete(item)
    session.commit()


def _seed(session, symbol: str, market: str) -> None:
    session.add(
        WatchlistItem(
            symbol=symbol,
            market=market,
            display_name=symbol,
            is_active=True,
            alert_threshold=None,
            alert_mode="fixed",
        )
    )
    session.commit()


def _requested(mock) -> set[str]:
    out: set[str] = set()
    for call in mock.call_args_list:
        for ns in call.args[0]:
            out.add(ns.symbol)
    return out


def test_a_share_uses_tencent_as_primary_source() -> None:
    """A 股必须先问腾讯，不能再让 Yahoo 的陈旧 ok 数据落库。"""
    service = QuoteService()

    with SessionLocal() as session:
        _reset(session)
        _seed(session, CN_SYMBOL, "cn")

        with (
            patch.object(
                service.fallback_provider,
                "fetch_quotes_batch",
                return_value=[_record(CN_SYMBOL, "cn", 211.9, "tencent")],
            ) as tencent,
            patch.object(service.provider, "fetch_quotes_batch", return_value=[]) as yahoo,
        ):
            payload = service.refresh_watchlist_quotes(session, force=True)

        assert CN_SYMBOL in _requested(tencent)
        assert CN_SYMBOL not in _requested(yahoo), "腾讯已成功，不应再打 Yahoo"
        row = next(item for item in payload if item["symbol"] == CN_SYMBOL)
        assert row["price"] == 211.9
        assert row["source"] == "tencent"

        _reset(session)


def test_us_equity_stays_on_yahoo() -> None:
    """美股腾讯不支持，主源必须仍是 Yahoo。"""
    service = QuoteService()

    with SessionLocal() as session:
        _reset(session)
        _seed(session, US_SYMBOL, "us")

        with (
            patch.object(
                service.provider,
                "fetch_quotes_batch",
                return_value=[_record(US_SYMBOL, "us", 336.26, "yahoo_finance")],
            ) as yahoo,
            patch.object(service.fallback_provider, "fetch_quotes_batch", return_value=[]) as tencent,
        ):
            payload = service.refresh_watchlist_quotes(session, force=True)

        assert US_SYMBOL in _requested(yahoo)
        assert US_SYMBOL not in _requested(tencent)
        row = next(item for item in payload if item["symbol"] == US_SYMBOL)
        assert row["price"] == 336.26

        _reset(session)


def test_a_share_falls_back_to_yahoo_when_tencent_fails() -> None:
    """腾讯挂了要能降级回 Yahoo，不能把 A 股打成 unavailable。"""
    service = QuoteService()

    with SessionLocal() as session:
        _reset(session)
        _seed(session, CN_SYMBOL, "cn")

        with (
            patch.object(
                service.fallback_provider,
                "fetch_quotes_batch",
                return_value=[_record(CN_SYMBOL, "cn", 0.0, "tencent", status="fetch_failed")],
            ),
            patch.object(
                service.provider,
                "fetch_quotes_batch",
                return_value=[_record(CN_SYMBOL, "cn", 199.18, "yahoo_finance")],
            ) as yahoo,
        ):
            payload = service.refresh_watchlist_quotes(session, force=True)

        assert CN_SYMBOL in _requested(yahoo)
        row = next(item for item in payload if item["symbol"] == CN_SYMBOL)
        assert row["status"] == "ok"
        assert row["price"] == 199.18

        _reset(session)


def test_mixed_watchlist_splits_by_market_without_cross_calls() -> None:
    """混合自选股：两个市场各走各的主源，互不牵连。"""
    service = QuoteService()

    with SessionLocal() as session:
        _reset(session)
        _seed(session, CN_SYMBOL, "cn")
        _seed(session, US_SYMBOL, "us")

        with (
            patch.object(
                service.fallback_provider,
                "fetch_quotes_batch",
                return_value=[_record(CN_SYMBOL, "cn", 211.9, "tencent")],
            ) as tencent,
            patch.object(
                service.provider,
                "fetch_quotes_batch",
                return_value=[_record(US_SYMBOL, "us", 336.26, "yahoo_finance")],
            ) as yahoo,
        ):
            payload = service.refresh_watchlist_quotes(session, force=True)

        # 只断言本用例的两个标的各自的归属；测试库里可能残留其它用例的自选股行，
        # 用相等断言会被它们干扰。
        assert CN_SYMBOL in _requested(tencent)
        assert CN_SYMBOL not in _requested(yahoo)
        assert US_SYMBOL in _requested(yahoo)
        assert US_SYMBOL not in _requested(tencent)
        by_symbol = {row["symbol"]: row for row in payload}
        assert by_symbol[CN_SYMBOL]["price"] == 211.9
        assert by_symbol[US_SYMBOL]["price"] == 336.26

        _reset(session)


def test_on_demand_single_quote_uses_tencent_first_for_a_share() -> None:
    """按需即时抓取（新加自选股的零延迟保底）同样要按市场选主源。"""
    service = QuoteService()

    with SessionLocal() as session:
        _reset(session)
        _seed(session, CN_SYMBOL, "cn")

        with (
            patch.object(
                service.fallback_provider,
                "fetch_quote",
                return_value=_record(CN_SYMBOL, "cn", 211.9, "tencent"),
            ) as tencent,
            patch.object(service.provider, "fetch_quote") as yahoo,
        ):
            payload = service.get_cached_symbol_quote(CN_SYMBOL, session)

        assert tencent.called
        assert not yahoo.called, "腾讯已成功，不应再打 Yahoo"
        assert payload["price"] == 211.9

        _reset(session)


def test_yahoo_batch_window_survives_a_nan_close_on_the_latest_row() -> None:
    """Yahoo 批量路径：当日 Close 为 NaN 时仍要能算出昨收。

    period="2d" 时窗口里只有两根，最新那根被 dropna 丢掉后只剩一根，
    ``iloc[-2]`` 取不到 → previous_close/change 全 None（页面"昨收 --"）。
    窗口放宽后，即使最新一根不可用，也仍有前一交易日可当昨收。
    """
    import pandas as pd

    from app.services.quote_provider import (
        YahooFinanceQuoteProvider,
        normalize_symbol,
    )

    provider = YahooFinanceQuoteProvider()
    ns = normalize_symbol(CN_SYMBOL, "cn")

    index = pd.to_datetime(["2026-07-23", "2026-07-24", "2026-07-27"])
    frame = pd.DataFrame(
        {
            ("002384.SZ", "Open"): [223.0, 199.11, 199.11],
            ("002384.SZ", "High"): [224.03, 205.83, 211.50],
            ("002384.SZ", "Low"): [198.99, 196.98, 188.88],
            ("002384.SZ", "Close"): [206.65, 199.18, float("nan")],
            ("002384.SZ", "Volume"): [123095564, 72822591, 82758019],
        },
        index=index,
    )
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)

    captured: dict[str, object] = {}

    def fake_download(**kwargs):
        captured.update(kwargs)
        return frame

    with patch("yfinance.download", side_effect=fake_download):
        records = provider._fetch_quotes_download([ns])

    # 窗口必须宽于 2 天，否则丢掉当日行后无从计算昨收。
    assert captured["period"] not in ("1d", "2d")
    record = records[ns.symbol]
    assert record.price == 199.18
    assert record.previous_close == 206.65
    assert record.change_percent is not None
