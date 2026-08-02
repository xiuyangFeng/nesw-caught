"""MarketOverviewService 单元测试（计划任务 B3）。

覆盖：
- 配置表为空时回落内置默认清单（含 ^VIX 与 kind=etf 条目）
- 指数 ticker 直接构造 NormalizedSymbol 走 YahooFinanceQuoteProvider.fetch_quotes_batch，
  不经过 normalize_symbol（000300.SS 不被改写成 000300.SH、不路由腾讯源）
- "先联网后写库"两阶段纪律：fetch_quotes_batch 调用时写事务内无待写对象
- 批量落库 price_snapshot；provider 失败行不回写
- 配置表非空时只用配置条目（含 enabled 过滤）
- list_index_quotes join 最新快照
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.price_snapshot import PriceSnapshot
from app.repositories.market_overview_repository import MarketOverviewRepository
from app.services.market_overview_service import (
    DEFAULT_INDEX_CONFIGS,
    VIX_SYMBOL,
    MarketOverviewService,
)
from app.services.quote_provider import QuoteRecord


def _make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    return testing_session


def _ok_record(symbol: str, market: str, price: float = 100.0, change_percent: float = 0.5) -> QuoteRecord:
    return QuoteRecord(
        symbol=symbol,
        market=market,
        provider_symbol=symbol,
        price=price,
        change_amount=price * change_percent / 100,
        change_percent=change_percent,
        open_price=price - 1,
        previous_close=price / (1 + change_percent / 100),
        day_high=price + 1,
        day_low=price - 2,
        volume=None,
        status="ok",
        source="yahoo_finance",
        message=None,
        fetched_at=datetime.now(UTC),
    )


def _failed_record(symbol: str, market: str) -> QuoteRecord:
    return QuoteRecord(
        symbol=symbol,
        market=market,
        provider_symbol=symbol,
        price=None,
        change_amount=None,
        change_percent=None,
        open_price=None,
        previous_close=None,
        day_high=None,
        day_low=None,
        volume=None,
        status="fetch_failed",
        source="yahoo_finance",
        message="simulated provider failure",
        fetched_at=datetime.now(UTC),
    )


def test_default_config_fallback_contains_vix_and_etf_entries() -> None:
    symbols = {(entry.symbol, entry.market, entry.kind) for entry in DEFAULT_INDEX_CONFIGS}

    assert (VIX_SYMBOL, "us", "index") in symbols
    assert ("^GSPC", "us", "index") in symbols
    assert ("000300.SS", "cn", "index") in symbols
    assert ("^KS11", "kr", "index") in symbols
    assert ("^N225", "jp", "index") in symbols
    assert ("^STOXX50E", "eu", "index") in symbols
    # 美/欧板块代理 ETF 入默认清单（kind=etf）。
    assert ("XLK", "us", "etf") in symbols
    assert any(market == "eu" and kind == "etf" for _, market, kind in symbols)


def test_refresh_falls_back_to_default_configs_and_calls_yahoo_directly() -> None:
    testing_session = _make_session()
    provider = MagicMock()
    provider.fetch_quotes_batch.side_effect = lambda normalized_list: [
        _ok_record(ns.symbol, ns.market) for ns in normalized_list
    ]
    service = MarketOverviewService(provider=provider)

    with testing_session() as session:
        service.refresh_index_quotes(session)

    provider.fetch_quotes_batch.assert_called_once()
    (normalized_list,), _ = provider.fetch_quotes_batch.call_args
    by_symbol = {ns.symbol: ns for ns in normalized_list}
    # 内置默认清单全量下发（表为空回落）。
    assert set(by_symbol) == {entry.symbol for entry in DEFAULT_INDEX_CONFIGS}
    # 关键纪律：直接构造 NormalizedSymbol，provider_symbol 保留原始 Yahoo ticker，
    # 000300.SS 不被 normalize_symbol 改写为 000300.SH（也就不会被路由到腾讯源）。
    assert by_symbol["000300.SS"].provider_symbol == "000300.SS"
    assert by_symbol["000300.SS"].market == "cn"
    assert by_symbol[VIX_SYMBOL].provider_symbol == VIX_SYMBOL
    assert by_symbol["^GSPC"].provider_symbol == "^GSPC"


def test_refresh_uses_config_table_when_not_empty_and_skips_disabled() -> None:
    testing_session = _make_session()
    provider = MagicMock()
    provider.fetch_quotes_batch.side_effect = lambda normalized_list: [
        _ok_record(ns.symbol, ns.market) for ns in normalized_list
    ]
    service = MarketOverviewService(provider=provider)

    with testing_session() as session:
        repo = MarketOverviewRepository(session)
        repo.create(symbol="^GSPC", market="us", display_name="标普500")
        repo.create(symbol="^FTSE", market="eu", display_name="富时100", enabled=False)
        session.commit()

        service.refresh_index_quotes(session)

    (normalized_list,), _ = provider.fetch_quotes_batch.call_args
    assert [ns.symbol for ns in normalized_list] == ["^GSPC"]


def test_refresh_fetches_network_before_opening_write_transaction() -> None:
    """两阶段纪律：provider 网络抓取完成前，session 不得有任何待写对象。"""
    testing_session = _make_session()
    pending_at_fetch_time: list[int] = []

    with testing_session() as session:
        def fake_fetch(normalized_list):
            pending_at_fetch_time.append(len(session.new))
            return [_ok_record(ns.symbol, ns.market) for ns in normalized_list]

        provider = MagicMock()
        provider.fetch_quotes_batch.side_effect = fake_fetch
        service = MarketOverviewService(provider=provider)

        service.refresh_index_quotes(session)

        assert pending_at_fetch_time == [0]
        # 写事务在 refresh 返回前已提交，快照可直接查到。
        rows = session.scalars(select(PriceSnapshot)).all()
        assert len(rows) == len(DEFAULT_INDEX_CONFIGS)
        gspc = next(row for row in rows if row.symbol == "^GSPC")
        assert gspc.market == "us"
        assert gspc.provider_name == "yahoo_finance"
        assert gspc.quote_status == "ok"


def test_refresh_does_not_persist_failed_records() -> None:
    testing_session = _make_session()
    provider = MagicMock()
    provider.fetch_quotes_batch.side_effect = lambda normalized_list: [
        _ok_record(ns.symbol, ns.market) if ns.symbol != "^N225" else _failed_record(ns.symbol, ns.market)
        for ns in normalized_list
    ]
    service = MarketOverviewService(provider=provider)

    with testing_session() as session:
        records = service.refresh_index_quotes(session)

        assert any(record.status == "fetch_failed" for record in records)
        rows = session.scalars(select(PriceSnapshot)).all()
        assert len(rows) == len(DEFAULT_INDEX_CONFIGS) - 1
        assert all(row.symbol != "^N225" for row in rows)


def test_list_index_quotes_joins_latest_snapshot() -> None:
    testing_session = _make_session()
    provider = MagicMock()
    provider.fetch_quotes_batch.side_effect = lambda normalized_list: [
        _ok_record(ns.symbol, ns.market, price=6450.12, change_percent=0.82)
        for ns in normalized_list
    ]
    service = MarketOverviewService(provider=provider)

    with testing_session() as session:
        service.refresh_index_quotes(session)
        quotes = service.list_index_quotes(session)

    by_symbol = {quote.symbol: quote for quote in quotes}
    assert set(by_symbol) == {entry.symbol for entry in DEFAULT_INDEX_CONFIGS}
    gspc = by_symbol["^GSPC"]
    assert gspc.display_name == "标普500"
    assert gspc.kind == "index"
    assert gspc.price == pytest.approx(6450.12)
    assert gspc.change_percent == pytest.approx(0.82)
    assert gspc.status == "ok"
    assert gspc.fetched_at is not None
    # ETF 条目也在配置清单中（板块区展示用）。
    assert by_symbol["XLK"].kind == "etf"


def test_list_index_quotes_marks_missing_snapshot_unavailable() -> None:
    testing_session = _make_session()
    service = MarketOverviewService(provider=MagicMock())

    with testing_session() as session:
        quotes = service.list_index_quotes(session)

    assert quotes
    assert all(quote.price is None for quote in quotes)
    assert all(quote.status == "unavailable" for quote in quotes)
    assert all(quote.fetched_at is None for quote in quotes)
