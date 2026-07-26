"""WS-3：行情 / 市场路由的阻塞与崩溃修复回归测试。

覆盖四类问题：

1. **必崩路径**（P0）：``QuoteService.get_cached_symbol_quote`` 的“零延迟保底”
   分支引用了未导入的 ``SessionLocal``，异常处理里又引用了未定义的 ``logger``，
   于是“刚加入自选股立刻查看行情”必定 500。这条路径此前**完全没有测试覆盖**，
   所以本文件第一组用例是最重要的锁死点。
2. **写事务跨网络**（P0）：``refresh_watchlist_quotes`` 此前先 flush（开启 SQLite
   写事务）再发起腾讯回落的 HTTP 抓取，写锁横跨网络调用。断言所有网络调用都发生
   在第一次落库之前，且整轮只 commit 一次。
3. **请求线程里的串行外部网络**（P1）：sparklines / calendar 改并发 + 整批超时；
   ``/market/search`` 的 Yahoo 在线搜索必须快速降级到本地结果。
4. **/health 不得触发外网调用**（P1）：X monitor 探针（最长 60s）必须移出请求路径。

全部用 monkeypatch / fake 替代真实外网调用，测试不依赖任何真实网络。
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes import market as market_route_module
from app.db.session import SessionLocal
from app.main import app
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist_item import WatchlistItem
from app.services import calendar_service as calendar_module
from app.services import market_chart_service as market_chart_module
from app.services import quote_service as quote_service_module
from app.services.calendar_service import CalendarService, clear_calendar_cache
from app.services.market_chart_service import MarketChartService
from app.services.quote_provider import NormalizedSymbol, QuoteRecord
from app.services.quote_service import QuoteService

# ---------------------------------------------------------------------------
# 公共构造工具
# ---------------------------------------------------------------------------


def _quote_record(symbol: str, market: str = "us", *, status: str = "ok", price: float = 123.45) -> QuoteRecord:
    return QuoteRecord(
        symbol=symbol,
        market=market,
        provider_symbol=symbol,
        price=price,
        change_amount=1.5,
        change_percent=1.23,
        open_price=price - 1,
        previous_close=price - 1.5,
        day_high=price + 2,
        day_low=price - 3,
        volume=10000,
        status=status,
        source="yahoo_finance" if status == "ok" else "yahoo_finance",
        message=None if status == "ok" else "boom",
        fetched_at=datetime.now(UTC),
    )


def _delete_symbols(symbols: list[str]) -> None:
    with SessionLocal() as session:
        for symbol in symbols:
            session.query(PriceSnapshot).filter(PriceSnapshot.symbol == symbol).delete()
            session.query(WatchlistItem).filter(WatchlistItem.symbol == symbol).delete()
        session.commit()


# ---------------------------------------------------------------------------
# 1. P0 回归：零延迟保底分支必崩（NameError）
# ---------------------------------------------------------------------------


def test_quote_service_module_defines_session_local_and_logger() -> None:
    """静态锁死：这两个名字缺失就是那条必崩路径的根因。"""
    assert hasattr(quote_service_module, "SessionLocal")
    assert hasattr(quote_service_module, "logger")


def test_on_demand_quote_fetch_does_not_raise_name_error() -> None:
    """无快照 -> 走“零延迟保底”分支 -> provider 返回 ok -> 正常返回并落库。

    修复前：``with SessionLocal() as local_session`` 抛 NameError，被 except 接住后
    ``logger.warning`` 再抛第二个 NameError -> 500。
    """
    symbol = "WSTHREEA"
    _delete_symbols([symbol])
    service = QuoteService()
    record = _quote_record(symbol)

    try:
        with SessionLocal() as session:
            with patch.object(service.provider, "fetch_quote", return_value=record) as fetch_mock:
                payload = service.get_cached_symbol_quote(symbol, session)

        assert fetch_mock.call_count == 1
        assert payload["symbol"] == symbol
        assert payload["status"] == "ok"
        assert payload["price"] == pytest.approx(123.45)

        # 保底抓取的结果必须真的落库，下一次读取才能直接命中快照。
        with SessionLocal() as session:
            persisted = (
                session.query(PriceSnapshot)
                .filter(PriceSnapshot.symbol == symbol)
                .one_or_none()
            )
            assert persisted is not None
            assert persisted.price == pytest.approx(123.45)
    finally:
        _delete_symbols([symbol])


def test_on_demand_quote_fetch_failure_degrades_instead_of_crashing() -> None:
    """provider 抛异常时走 ``logger.warning`` 分支：不得再抛 NameError，应优雅降级。"""
    symbol = "WSTHREEB"
    _delete_symbols([symbol])
    service = QuoteService()

    try:
        with SessionLocal() as session:
            with patch.object(service.provider, "fetch_quote", side_effect=RuntimeError("provider down")):
                payload = service.get_cached_symbol_quote(symbol, session)

        assert payload["symbol"] == symbol
        assert payload["status"] == "unavailable"
        assert payload["price"] is None
    finally:
        _delete_symbols([symbol])


def test_symbol_quote_route_survives_missing_snapshot(monkeypatch) -> None:
    """端到端：GET /api/market/symbols/{s} 在无快照时不能 500。"""
    symbol = "WSTHREEC"
    _delete_symbols([symbol])

    record = _quote_record(symbol)
    monkeypatch.setattr(
        "app.services.quote_provider.YahooFinanceQuoteProvider.fetch_quote",
        lambda self, normalized: record,
    )

    try:
        client = TestClient(app)
        response = client.get(f"/api/market/symbols/{symbol}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["symbol"] == symbol
        assert payload["status"] == "ok"
    finally:
        _delete_symbols([symbol])


# ---------------------------------------------------------------------------
# 2. P0：写事务不得跨网络
# ---------------------------------------------------------------------------


def test_refresh_watchlist_quotes_finishes_all_network_before_write_transaction() -> None:
    """调用序列断言：所有 fetch 都在第一次落库之前，且整轮只 commit 一次。

    修复前的顺序是 fetch:yahoo -> save -> fetch:tencent -> save -> commit，
    也就是 SQLite 写锁横跨了腾讯回落的 HTTP 调用。
    """
    symbols = ["600991.SH", "000991.SZ"]
    _delete_symbols(symbols)
    service = QuoteService()
    events: list[str] = []

    items = [
        WatchlistItem(symbol=symbols[0], market="cn", display_name="甲", is_active=True),
        WatchlistItem(symbol=symbols[1], market="cn", display_name="乙", is_active=True),
    ]

    def fake_yahoo_batch(ns_list):
        events.append("fetch:yahoo")
        return [_quote_record(ns.symbol, ns.market, status="fetch_failed") for ns in ns_list]

    def fake_tencent_batch(ns_list):
        events.append("fetch:tencent")
        return [_quote_record(ns.symbol, ns.market) for ns in ns_list]

    def fake_save(session, market_repo, quote, *, auto_commit=True):
        events.append(f"save:{quote.symbol}")
        assert auto_commit is False, "批量刷新必须走单次 commit，不能逐条提交"
        return PriceSnapshot(
            symbol=quote.symbol,
            market=quote.market,
            price=quote.price or 0.0,
            change_amount=quote.change_amount,
            change_percent=quote.change_percent,
            open_price=quote.open_price,
            previous_close=quote.previous_close,
            day_high=quote.day_high,
            day_low=quote.day_low,
            volume=quote.volume,
            provider_name=quote.source,
            provider_symbol=quote.provider_symbol,
            quote_status=quote.status,
            status_message=quote.message,
            fetched_at=quote.fetched_at,
        )

    try:
        with SessionLocal() as session:
            session.commit = lambda: events.append("commit")  # type: ignore[method-assign]
            with patch.object(quote_service_module.WatchlistRepository, "list_all", return_value=items), \
                    patch.object(service.provider, "fetch_quotes_batch", side_effect=fake_yahoo_batch), \
                    patch.object(service.fallback_provider, "fetch_quotes_batch", side_effect=fake_tencent_batch), \
                    patch.object(service, "_save_live_quote", side_effect=fake_save):
                payloads = service.refresh_watchlist_quotes(session)
    finally:
        _delete_symbols(symbols)

    assert len(payloads) == 2
    assert all(row["status"] == "ok" for row in payloads)

    fetch_indexes = [i for i, name in enumerate(events) if name.startswith("fetch:")]
    save_indexes = [i for i, name in enumerate(events) if name.startswith("save:")]
    assert fetch_indexes and save_indexes
    # 核心断言：写事务窗口（第一次 save 到 commit）内不得出现任何网络调用。
    assert max(fetch_indexes) < min(save_indexes)
    assert events.count("commit") == 1
    assert events[-1] == "commit"


def test_fallback_quote_chunks_are_fetched_concurrently() -> None:
    """腾讯回落的多标的抓取按块并发：N 块的总耗时应远小于 N × 单块耗时。"""
    service = QuoteService()
    chunk_seconds = 0.3
    ns_list = [
        NormalizedSymbol(symbol=f"6009{index:02d}.SH", market="cn", provider_symbol=f"6009{index:02d}.SS")
        for index in range(45)  # 45 个 -> 3 个分块（chunk size = 20）
    ]

    def slow_batch(chunk):
        time.sleep(chunk_seconds)
        return [_quote_record(ns.symbol, ns.market) for ns in chunk]

    with patch.object(service.fallback_provider, "fetch_quotes_batch", side_effect=slow_batch):
        started_at = time.monotonic()
        records = service._fetch_fallback_quotes(ns_list)
        elapsed = time.monotonic() - started_at

    assert len(records) == 45
    # 串行需要 3 × 0.3 = 0.9s；并发应接近 0.3s。
    assert elapsed < chunk_seconds * 2, f"fallback 抓取似乎仍是串行的：{elapsed:.2f}s"


def test_single_chunk_fallback_still_uses_one_batch_request() -> None:
    """单块时保持“一次批量请求”的原有语义，不额外拆分。"""
    service = QuoteService()
    ns_list = [NormalizedSymbol(symbol="600519.SH", market="cn", provider_symbol="600519.SS")]

    with patch.object(
        service.fallback_provider,
        "fetch_quotes_batch",
        return_value=[_quote_record("600519.SH", "cn")],
    ) as batch_mock:
        records = service._fetch_fallback_quotes(ns_list)

    batch_mock.assert_called_once()
    assert set(records) == {"600519.SH"}


# ---------------------------------------------------------------------------
# 3. P1：sparklines 并发 + 整批超时
# ---------------------------------------------------------------------------


def _sparkline_service_patches(service: MarketChartService, download):
    """统一打桩 sparklines 的三个出口（自选股校验 / 归一化 / 下载）。"""
    def fake_require(symbol: str, session):
        item = MagicMock()
        item.symbol = symbol
        item.market = "us"
        return item

    return (
        patch.object(service, "_require_watchlist_symbol", side_effect=fake_require),
        patch.object(
            market_chart_module,
            "normalize_symbol",
            side_effect=lambda symbol, market: NormalizedSymbol(symbol=symbol, market="us", provider_symbol=symbol),
        ),
        patch.object(service, "_download_history", side_effect=download),
    )


def _fake_history(prices: list[float]) -> MagicMock:
    frame = MagicMock()
    close_series = MagicMock()
    close_series.tail.return_value.dropna.return_value.tolist.return_value = prices
    frame.__getitem__.return_value = close_series
    return frame


def test_sparklines_download_symbols_concurrently() -> None:
    """8 个标的的总耗时应远小于 8 × 单个耗时（此前是循环内串行 yf.download）。"""
    service = MarketChartService()
    per_symbol_seconds = 0.3
    symbols = [f"SPKA{index}" for index in range(8)]

    def slow_download(provider_symbol, period, interval):
        time.sleep(per_symbol_seconds)
        return _fake_history([1.0, 2.0, 3.0])

    require_patch, normalize_patch, download_patch = _sparkline_service_patches(service, slow_download)
    with require_patch, normalize_patch, download_patch:
        started_at = time.monotonic()
        payload = service.get_sparklines(symbols, session=MagicMock())
        elapsed = time.monotonic() - started_at

    assert set(payload) == set(symbols)
    assert payload[symbols[0]] == {"prices": [1.0, 2.0, 3.0]}
    # 串行需要 8 × 0.3 = 2.4s；并发（max_workers>=8）应接近 0.3s。
    assert elapsed < per_symbol_seconds * 3, f"sparklines 似乎仍是串行的：{elapsed:.2f}s"


def test_sparklines_batch_timeout_returns_empty_series_instead_of_hanging(monkeypatch) -> None:
    """整批超时的标的返回空序列（前端显示“暂无数据”），请求不得被挂住。"""
    service = MarketChartService()
    monkeypatch.setattr(market_chart_module, "_SPARKLINE_BATCH_TIMEOUT_SECONDS", 0.3)

    def hanging_download(provider_symbol, period, interval):
        time.sleep(2.0)
        return _fake_history([1.0])

    require_patch, normalize_patch, download_patch = _sparkline_service_patches(service, hanging_download)
    with require_patch, normalize_patch, download_patch:
        started_at = time.monotonic()
        payload = service.get_sparklines(["SPKB1", "SPKB2"], session=MagicMock())
        elapsed = time.monotonic() - started_at

    assert elapsed < 1.5, f"sparklines 整批超时未生效：{elapsed:.2f}s"
    assert payload == {"SPKB1": {"prices": []}, "SPKB2": {"prices": []}}


def test_sparklines_releases_db_session_before_network() -> None:
    """联网之前必须先结束只读事务，避免整段抓取期间攥着 SQLite 连接。"""
    service = MarketChartService()
    session = MagicMock()
    order: list[str] = []

    session.rollback.side_effect = lambda: order.append("release")

    def tracked_download(provider_symbol, period, interval):
        order.append("download")
        return _fake_history([1.0])

    require_patch, normalize_patch, download_patch = _sparkline_service_patches(service, tracked_download)
    with require_patch, normalize_patch, download_patch:
        service.get_sparklines(["SPKC1"], session=session)

    assert order == ["release", "download"]


# ---------------------------------------------------------------------------
# 4. P1：/health 不得触发外部网络
# ---------------------------------------------------------------------------


def test_health_endpoint_never_calls_twitterapi(monkeypatch) -> None:
    """/health 是前端轮询接口，绝不能在请求线程里发起 twitterapi.io 探针。"""
    calls: list[str] = []

    def forbidden_request(self, path, params, *, apply_rate_limit=True):  # pragma: no cover - 不应被调用
        calls.append(path)
        raise AssertionError("health check must not perform external twitterapi.io calls")

    monkeypatch.setattr(
        "app.services.twitterapi_io_client.TwitterApiIoClient._request",
        forbidden_request,
    )

    class ForbiddenXMonitorService:  # pragma: no cover - 不应被实例化
        def __init__(self, session) -> None:
            calls.append("XMonitorService()")
            raise AssertionError("health check must not construct XMonitorService")

    monkeypatch.setattr("app.api.routes.health.XMonitorService", ForbiddenXMonitorService)
    monkeypatch.setattr(
        "app.api.routes.health.get_settings",
        lambda: SimpleNamespace(
            app_name="News Caught Backend",
            environment="test",
            stream_mode="sse",
            ai_enabled=False,
            x_monitor_enabled=True,
            twitterapi_io_api_key="test-key",
            x_monitor_refresh_cooldown_hours=3,
        ),
    )

    client = TestClient(app)
    started_at = time.monotonic()
    response = client.get("/api/health")
    elapsed = time.monotonic() - started_at

    assert response.status_code == 200
    assert calls == []
    # 未探测过 / 记录陈旧 -> unknown -> False（schema 字段保持不变）。
    assert response.json()["x_monitor_healthy"] is False
    assert elapsed < 2.0, f"/health 疑似仍在请求路径里联网：{elapsed:.2f}s"


def test_health_reports_x_monitor_healthy_from_recorded_probe(monkeypatch) -> None:
    """有新鲜的后台探测记录时，/health 直接复用它（纯 DB 读，零网络）。"""
    from app.models.x_source_health import XSourceHealth
    from app.services.x_monitor import PROVIDER_NAME

    monkeypatch.setattr(
        "app.api.routes.health.get_settings",
        lambda: SimpleNamespace(
            app_name="News Caught Backend",
            environment="test",
            stream_mode="sse",
            ai_enabled=False,
            x_monitor_enabled=True,
            twitterapi_io_api_key="test-key",
            x_monitor_refresh_cooldown_hours=3,
        ),
    )

    with SessionLocal() as session:
        session.query(XSourceHealth).filter(XSourceHealth.provider_name == PROVIDER_NAME).delete()
        session.add(
            XSourceHealth(
                provider_name=PROVIDER_NAME,
                last_success_at=datetime.now(UTC) - timedelta(minutes=5),
                consecutive_failures=0,
                total_fetches=3,
                total_failures=0,
            )
        )
        session.commit()

    try:
        client = TestClient(app)
        assert client.get("/api/health").json()["x_monitor_healthy"] is True

        # 陈旧记录 -> 视为 unknown -> False。
        with SessionLocal() as session:
            row = session.query(XSourceHealth).filter(XSourceHealth.provider_name == PROVIDER_NAME).one()
            row.last_success_at = datetime.now(UTC) - timedelta(days=30)
            session.commit()

        assert client.get("/api/health").json()["x_monitor_healthy"] is False
    finally:
        with SessionLocal() as session:
            session.query(XSourceHealth).filter(XSourceHealth.provider_name == PROVIDER_NAME).delete()
            session.commit()


# ---------------------------------------------------------------------------
# 5. P1：calendar 并发 + 整批超时
# ---------------------------------------------------------------------------


class _SlowTicker:
    def __init__(self, seconds: float) -> None:
        self._seconds = seconds

    @property
    def calendar(self):
        time.sleep(self._seconds)
        return {}

    def get_earnings_dates(self, limit=12):
        return None


@pytest.fixture(autouse=True)
def _clear_calendar_cache():
    clear_calendar_cache()
    yield
    clear_calendar_cache()


def _calendar_items(count: int) -> list[WatchlistItem]:
    return [
        WatchlistItem(symbol=f"CALPERF{index}", market="us", display_name=f"CAL {index}", is_active=True)
        for index in range(count)
    ]


def test_calendar_fetches_symbols_concurrently() -> None:
    """冷启动（缓存全空）时逐 symbol 串行 yfinance 会把 /calendar 拖到 N × 单次耗时。"""
    per_symbol_seconds = 0.3
    items = _calendar_items(8)

    with SessionLocal() as session, \
            patch.object(calendar_module.WatchlistRepository, "list_all", return_value=items), \
            patch.object(calendar_module, "_make_ticker", side_effect=lambda sym: _SlowTicker(per_symbol_seconds)):
        started_at = time.monotonic()
        result = CalendarService(snapshot_enabled=False).get_upcoming_events(session, days=30)
        elapsed = time.monotonic() - started_at

    assert result["skipped_count"] == 0
    assert len(result["summaries"]) == 8
    # 串行需要 8 × 0.3 = 2.4s；并发应接近 0.3s。
    assert elapsed < per_symbol_seconds * 3, f"calendar 似乎仍是串行抓取：{elapsed:.2f}s"


def test_calendar_batch_timeout_skips_slow_symbols(monkeypatch) -> None:
    """整批超时的 symbol 计入 skipped，绝不拖住 /calendar 请求。"""
    monkeypatch.setattr(calendar_module, "_CALENDAR_BATCH_TIMEOUT_SECONDS", 0.3)
    items = _calendar_items(2)

    with SessionLocal() as session, \
            patch.object(calendar_module.WatchlistRepository, "list_all", return_value=items), \
            patch.object(calendar_module, "_make_ticker", side_effect=lambda sym: _SlowTicker(2.0)):
        started_at = time.monotonic()
        result = CalendarService(snapshot_enabled=False).get_upcoming_events(session, days=30)
        elapsed = time.monotonic() - started_at

    assert elapsed < 1.5, f"calendar 整批超时未生效：{elapsed:.2f}s"
    assert result["skipped_count"] == 2
    assert result["events"] == []


def test_calendar_releases_db_session_before_network() -> None:
    session = MagicMock()
    order: list[str] = []
    session.rollback.side_effect = lambda: order.append("release")

    def tracked_ticker(provider_symbol):
        order.append("fetch")
        return _SlowTicker(0.0)

    with patch.object(calendar_module.WatchlistRepository, "list_all", return_value=_calendar_items(1)), \
            patch.object(calendar_module, "_make_ticker", side_effect=tracked_ticker):
        CalendarService(snapshot_enabled=False).get_upcoming_events(session, days=30)

    assert order == ["release", "fetch"]


# ---------------------------------------------------------------------------
# 6. P1：/market/search 的 Yahoo 在线搜索必须快速降级
# ---------------------------------------------------------------------------


def test_market_search_degrades_fast_when_yahoo_hangs(monkeypatch) -> None:
    """Yahoo 卡住（DNS/TLS 建连不计入 httpx timeout）时，请求必须在预算内返回本地结果。"""
    monkeypatch.setattr(market_route_module, "_YAHOO_SEARCH_BUDGET_SECONDS", 0.3)

    def hanging_get(*args, **kwargs):
        time.sleep(2.0)
        raise RuntimeError("should have been abandoned")

    monkeypatch.setattr("httpx.get", hanging_get)

    client = TestClient(app)
    started_at = time.monotonic()
    response = client.get("/api/market/search?q=ZZQQWS3")
    elapsed = time.monotonic() - started_at

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert elapsed < 1.5, f"/market/search 被 Yahoo 拖住了：{elapsed:.2f}s"
