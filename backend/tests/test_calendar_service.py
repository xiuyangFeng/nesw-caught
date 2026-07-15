"""财报 / 事件日历服务测试。

全程用假 Ticker 替换 yfinance 出口 ``_make_ticker``，绝不联网。为与测试库里的
demo 自选股数据完全隔离、让断言确定化，这里打桩 ``WatchlistRepository.list_all``
返回内存中构造的自选项（不落库）。覆盖：事件解析、days_until 计算、按日期升序、
窗口过滤、过去事件排除、失败 symbol 跳过并计数、每只 symbol 最近财报摘要、
TTL 缓存命中（第二次不再调用 yfinance）。
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.db.session import SessionLocal
from app.models.watchlist_item import WatchlistItem
from app.services import calendar_service as calendar_module
from app.services.calendar_service import CalendarService, clear_calendar_cache

# 测试用自选股 symbol（纯字母 -> 归一化为美股，provider_symbol 与 symbol 相同）。
SYM_A = "CALTSTA"
SYM_B = "CALTSTB"
SYM_C = "CALTSTC"
SYM_D = "CALTSTD"


def _today():
    return datetime.now(UTC).date()


def _d(days: int):
    return _today() + timedelta(days=days)


class FakeEarningsFrame:
    """模拟 get_earnings_dates 返回的 DataFrame，仅暴露 index / empty。"""

    def __init__(self, dates):
        self.index = list(dates)

    @property
    def empty(self):
        return len(self.index) == 0


class FakeTicker:
    def __init__(self, calendar=None, earnings_frame=None):
        self._calendar = calendar
        self._earnings_frame = earnings_frame if earnings_frame is not None else FakeEarningsFrame([])

    @property
    def calendar(self):
        return self._calendar

    def get_earnings_dates(self, limit=12):
        return self._earnings_frame


@pytest.fixture(autouse=True)
def _clean_cache():
    clear_calendar_cache()
    yield
    clear_calendar_cache()


def _item(symbol: str) -> WatchlistItem:
    # 内存构造，不 add 进 session；仅用于属性访问。
    return WatchlistItem(symbol=symbol, market="us", display_name=f"{symbol} Inc", is_active=True)


def _service():
    # 关闭快照落盘，避免测试留下磁盘产物。
    return CalendarService(snapshot_enabled=False)


def _ticker_factory(mapping):
    """返回一个 _make_ticker 替身：按 provider_symbol 分发假 Ticker。

    mapping 的值若为 Exception 实例则抛出（模拟抓取失败）。
    """

    def factory(provider_symbol):
        entry = mapping.get(provider_symbol)
        if isinstance(entry, Exception):
            raise entry
        if entry is None:
            return FakeTicker()
        return entry

    return factory


def _run_upcoming(symbols, mapping, days=30, make_ticker=None):
    """在打桩 list_all + _make_ticker 的前提下运行 get_upcoming_events。"""
    items = [_item(sym) for sym in symbols]
    make = make_ticker if make_ticker is not None else MagicMock(side_effect=_ticker_factory(mapping))
    with SessionLocal() as session, \
            patch.object(calendar_module.WatchlistRepository, "list_all", return_value=items), \
            patch.object(calendar_module, "_make_ticker", make):
        result = _service().get_upcoming_events(session, days=days)
    return result, make


def test_parse_events_days_until_and_sorting():
    mapping = {
        # A：财报 +5、除息 +10，另有一个 +40（超出 30 天窗口，应被排除）。
        SYM_A: FakeTicker(calendar={"Earnings Date": [_d(5), _d(40)], "Ex-Dividend Date": _d(10)}),
        # B：财报 +2（应排在最前）。
        SYM_B: FakeTicker(calendar={"Earnings Date": [_d(2)]}),
    }
    result, _ = _run_upcoming([SYM_A, SYM_B], mapping, days=30)

    events = result["events"]
    # 窗口内应有 3 条：B 财报 +2、A 财报 +5、A 除息 +10（A 的 +40 被窗口排除）。
    assert len(events) == 3
    # 升序排列。
    assert [e["days_until"] for e in events] == [2, 5, 10]
    assert events[0]["symbol"] == SYM_B and events[0]["event_type"] == "earnings"
    assert events[1]["symbol"] == SYM_A and events[1]["event_type"] == "earnings"
    assert events[2]["symbol"] == SYM_A and events[2]["event_type"] == "ex_dividend"
    # date 为 ISO 字符串。
    assert events[0]["date"] == _d(2).isoformat()
    # display_name 透传。
    assert events[0]["display_name"] == f"{SYM_B} Inc"

    # 每只 symbol 最近未来财报摘要。
    summaries = {s["symbol"]: s for s in result["summaries"]}
    assert summaries[SYM_A]["next_earnings_days_until"] == 5
    assert summaries[SYM_A]["next_earnings_date"] == _d(5).isoformat()
    assert summaries[SYM_B]["next_earnings_days_until"] == 2
    assert result["skipped_count"] == 0


def test_past_events_excluded():
    mapping = {
        SYM_A: FakeTicker(
            calendar={
                "Earnings Date": [_d(-3)],  # 过去财报，应排除
                "Ex-Dividend Date": _d(4),  # 未来除息，应保留
            }
        )
    }
    result, _ = _run_upcoming([SYM_A], mapping, days=30)

    assert [e["event_type"] for e in result["events"]] == ["ex_dividend"]
    # 无未来财报 -> 摘要为 None。
    summaries = {s["symbol"]: s for s in result["summaries"]}
    assert summaries[SYM_A]["next_earnings_days_until"] is None
    assert summaries[SYM_A]["next_earnings_date"] is None


def test_failed_symbol_skipped_and_counted():
    mapping = {
        SYM_A: FakeTicker(calendar={"Earnings Date": [_d(6)]}),
        SYM_C: RuntimeError("yfinance blew up"),
    }
    result, _ = _run_upcoming([SYM_A, SYM_C], mapping, days=30)

    # 隔离了 demo 数据，skipped_count 精确为 1（仅 SYM_C）。
    assert result["skipped_count"] == 1
    assert {e["symbol"] for e in result["events"]} == {SYM_A}
    summary_symbols = {s["symbol"] for s in result["summaries"]}
    assert SYM_A in summary_symbols
    assert SYM_C not in summary_symbols


def test_earnings_dates_fallback_source():
    """calendar 无 Earnings Date 时，用 get_earnings_dates 的 index 补齐财报日。"""
    mapping = {
        SYM_D: FakeTicker(
            calendar={"Ex-Dividend Date": _d(9)},
            earnings_frame=FakeEarningsFrame([_d(-2), _d(7)]),  # 过去 + 未来各一
        )
    }
    result, _ = _run_upcoming([SYM_D], mapping, days=30)

    types = sorted(e["event_type"] for e in result["events"])
    assert types == ["earnings", "ex_dividend"]
    summaries = {s["symbol"]: s for s in result["summaries"]}
    assert summaries[SYM_D]["next_earnings_days_until"] == 7


def test_ttl_cache_hit_avoids_second_fetch():
    mapping = {
        SYM_A: FakeTicker(calendar={"Earnings Date": [_d(5)]}),
        SYM_B: FakeTicker(calendar={"Earnings Date": [_d(3)]}),
    }
    items = [_item(SYM_A), _item(SYM_B)]
    mock_make = MagicMock(side_effect=_ticker_factory(mapping))
    with SessionLocal() as session, \
            patch.object(calendar_module.WatchlistRepository, "list_all", return_value=items), \
            patch.object(calendar_module, "_make_ticker", mock_make):
        first = _service().get_upcoming_events(session, days=30)
        calls_after_first = mock_make.call_count
        # 第二次（换新的 service 实例）应全部命中缓存，不再触碰 yfinance。
        second = _service().get_upcoming_events(session, days=30)
        calls_after_second = mock_make.call_count

    assert calls_after_first == 2  # A、B 各抓一次
    assert calls_after_second == 2  # 第二次 0 新增（全部命中缓存）
    assert [e["days_until"] for e in first["events"]] == [e["days_until"] for e in second["events"]]


def test_symbol_calendar_not_in_watchlist():
    """单只查询：即使不在自选股中也能返回，display_name 为 None。"""
    mapping = {SYM_A: FakeTicker(calendar={"Earnings Date": [_d(8)], "Ex-Dividend Date": _d(12)})}
    with SessionLocal() as session, \
            patch.object(calendar_module.WatchlistRepository, "get_by_symbol", return_value=None), \
            patch.object(calendar_module, "_make_ticker", side_effect=_ticker_factory(mapping)):
        result = _service().get_symbol_calendar(SYM_A, session, days=90)

    assert result["skipped_count"] == 0
    assert {e["event_type"] for e in result["events"]} == {"earnings", "ex_dividend"}
    summaries = {s["symbol"]: s for s in result["summaries"]}
    assert summaries[SYM_A]["next_earnings_days_until"] == 8
    assert summaries[SYM_A]["display_name"] is None
