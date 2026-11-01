"""站内提醒规则测试（聚焦改造 P2-T2）。

规则：
- 价格：仅持仓股（position_size > 0），|涨跌幅| >= 5%，只在该市场交易时段内、且当天已观察到
  价格变动（行情"活着"）时触发；按市场本地日期每天最多一次。节假日行情整天不变 → 不提醒；
  前一天平收（昨收不变）也不会挡住第二天的提醒。
- 新闻：标题出现股票简称/代码即命中；持仓立即提醒，仅关注的股票进入 30 分钟合并窗口；
  同一新闻同一股票只提醒一次。
- 静默时段（默认北京时间 22:00～08:00）：照常记录，overnight=True，次日 08:00 才可见，不推 SSE。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.db.session import SessionLocal
from app.models.alert import Alert
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.watchlist_item import WatchlistItem
from app.services.alert_service import AlertService

# 2026-11-02 是周一。北京时间 10:00 = UTC 02:00（A 股、港股盘中）。
MONDAY_10AM = datetime(2026, 11, 2, 2, 0, tzinfo=UTC)
MONDAY_23PM = datetime(2026, 11, 2, 15, 0, tzinfo=UTC)  # 北京时间 23:00


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _Bus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def publish(self, event: str, payload: dict) -> None:
        self.events.append((event, payload))


@pytest.fixture(autouse=True)
def _seed():
    with SessionLocal() as session:
        session.query(Alert).delete()
        session.query(NewsStockMention).delete()
        session.query(WatchlistItem).delete()
        session.add_all(
            [
                WatchlistItem(symbol="002384.SZ", market="cn", display_name="东山精密", position_size=199, average_cost=100),
                WatchlistItem(symbol="688256.SH", market="cn", display_name="寒武纪", position_size=1100, average_cost=100),
                WatchlistItem(symbol="9988.HK", market="hk", display_name="Alibaba", position_size=100, average_cost=100),
                WatchlistItem(symbol="HK2513", market="hk", display_name="智谱", position_size=None, average_cost=None),
            ]
        )
        session.commit()
    yield
    with SessionLocal() as session:
        session.query(Alert).delete()
        session.query(NewsStockMention).delete()
        session.query(NewsItem).filter(NewsItem.id == 303).delete()
        session.query(WatchlistItem).delete()
        session.commit()


def _service(now: datetime) -> tuple[AlertService, _Clock, _Bus]:
    clock = _Clock(now)
    bus = _Bus()
    service = AlertService(
        session_factory=SessionLocal,
        event_bus=bus,
        clock=clock,
        price_move_percent=5.0,
        quiet_hours=("22:00", "08:00"),
        tz_name="Asia/Shanghai",
        watch_digest_minutes=30,
    )
    return service, clock, bus


def _alerts() -> list[Alert]:
    with SessionLocal() as session:
        return list(session.query(Alert).order_by(Alert.id))


def _quote(symbol: str, change: float, *, prev: float = 100.0, market: str = "cn", price: float | None = None) -> dict:
    return {
        "symbol": symbol,
        "market": market,
        "display_name": None,
        "price": price if price is not None else prev * (1 + change / 100),
        "change_percent": change,
        "previous_close": prev,
    }


# ---------------------------------------------------------------- 价格


def _tick(service: AlertService, clock: _Clock, quotes: list[dict], seconds: int = 15) -> int:
    """推进时钟后喂一轮行情，返回本轮新建提醒数。"""
    clock.now += timedelta(seconds=seconds)
    return service.on_quotes(quotes)


def test_holding_price_move_alerts_once_per_trading_day() -> None:
    service, clock, bus = _service(MONDAY_10AM)

    # 当天第一次看到该股报价时还不能确认行情在动，先不提醒。
    assert service.on_quotes([_quote("688256.SH", 6.0)]) == 0
    assert _tick(service, clock, [_quote("688256.SH", 6.1)]) == 1
    assert _tick(service, clock, [_quote("688256.SH", 7.0)], seconds=300) == 0  # 同一交易日

    alerts = _alerts()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.kind == "holding_price_move"
    assert alert.severity == "immediate"
    assert alert.symbol == "688256.SH"
    assert "寒武纪" in alert.title and "6.10%" in alert.title
    assert alert.overnight is False
    assert [event for event, _ in bus.events] == ["alert.created"]


def test_price_move_respects_threshold_direction_and_holdings() -> None:
    service, clock, _ = _service(MONDAY_10AM)
    first = [
        _quote("002384.SZ", 4.9),
        _quote("688256.SH", -4.9),
        _quote("HK2513", 8.9, market="hk"),
        _quote("600519.SH", 7.9),
    ]
    service.on_quotes(first)

    created = _tick(
        service,
        clock,
        [
            _quote("002384.SZ", 4.99),  # 未到阈值
            _quote("688256.SH", -5.0),  # 跌 5% 触发
            _quote("HK2513", 9.0, market="hk"),  # 仅关注、无持仓：不做价格提醒
            _quote("600519.SH", 8.0),  # 不在自选
        ],
    )

    assert created == 1
    alert = _alerts()[0]
    assert alert.symbol == "688256.SH"
    assert "跌" in alert.title


def test_price_move_ignored_outside_trading_session() -> None:
    saturday = datetime(2026, 11, 7, 2, 0, tzinfo=UTC)
    service, clock, _ = _service(saturday)

    service.on_quotes([_quote("688256.SH", 6.0)])
    assert _tick(service, clock, [_quote("688256.SH", 6.1)]) == 0
    assert _alerts() == []


def test_stale_holiday_quotes_never_alert() -> None:
    service, clock, _ = _service(MONDAY_10AM)

    # 工作日休市（节假日）：交易时段判断认为开市，但行情整天停在上一个交易日的数据。
    for _ in range(20):
        assert _tick(service, clock, [_quote("688256.SH", 6.1, prev=100.0)], seconds=60) == 0
    assert _alerts() == []


def test_flat_close_does_not_block_next_day_alert() -> None:
    service, clock, _ = _service(MONDAY_10AM)
    service.on_quotes([_quote("688256.SH", 5.9, prev=100.0)])
    assert _tick(service, clock, [_quote("688256.SH", 6.1, prev=100.0)]) == 1

    # 周一收盘正好平收（收盘价 = 昨收 100），周二昨收仍是 100，盘中再跌 6%。
    clock.now = MONDAY_10AM + timedelta(days=1)
    service.on_quotes([_quote("688256.SH", -5.8, prev=100.0)])
    assert _tick(service, clock, [_quote("688256.SH", -6.0, prev=100.0)]) == 1
    assert len(_alerts()) == 2


# ---------------------------------------------------------------- 新闻


def test_holding_news_alerts_immediately_and_dedupes() -> None:
    service, _, bus = _service(MONDAY_10AM)

    payload = {"id": 101, "title": "东山精密拿下北美大客户新订单", "summary": None, "source_name": "CLS", "market": "cn"}
    assert service.on_news_batch([payload]) == 1
    assert service.on_news_batch([payload]) == 0

    alert = _alerts()[0]
    assert alert.kind == "holding_news"
    assert alert.symbol == "002384.SZ"
    assert alert.payload_json and "101" in alert.payload_json
    assert ("alert.created" in [event for event, _ in bus.events])


def test_news_matching_uses_codes_latin_names_and_rule_mentions() -> None:
    service, _, _ = _service(MONDAY_10AM)
    with SessionLocal() as session:
        session.add(NewsItem(id=303, source_name="s", source_url="u", title="科创板 AI 芯片龙头再获机构增持", canonical_url="c303", url_hash="h303", market="cn", language="zh", fetched_at=MONDAY_10AM, effective_at=MONDAY_10AM))
        session.flush()
        session.add(NewsStockMention(news_id=303, symbol="688256.SH", market="cn", mention_type="rule", confidence=0.95))
        session.commit()

    created = service.on_news_batch(
        [
            {"id": 301, "title": "688256 盘中涨停", "summary": None, "source_name": "s", "market": "cn"},
            {"id": 302, "title": "Alibaba beats estimates on cloud growth", "summary": None, "source_name": "s", "market": "us"},
            {"id": 303, "title": "科创板 AI 芯片龙头再获机构增持", "summary": None, "source_name": "s", "market": "cn"},
            {"id": 304, "title": "Alibabaesque startup raises funds", "summary": None, "source_name": "s", "market": "us"},
        ]
    )

    assert created == 3
    assert {(a.symbol, a.kind) for a in _alerts()} == {
        ("688256.SH", "holding_news"),
        ("9988.HK", "holding_news"),
    }
    assert len(_alerts()) == 3


def test_watch_only_news_is_merged_into_one_digest_per_window() -> None:
    service, clock, bus = _service(MONDAY_10AM)

    assert service.on_news_batch([{"id": 401, "title": "智谱发布新一代大模型", "summary": None, "source_name": "s", "market": "cn"}]) == 0
    assert service.on_news_batch([{"id": 402, "title": "智谱与多家车企合作", "summary": None, "source_name": "s", "market": "cn"}]) == 0
    assert _alerts() == []

    clock.now += timedelta(minutes=31)
    assert service.flush_watch_digest() == 1

    alerts = _alerts()
    assert len(alerts) == 1
    assert alerts[0].kind == "watch_news_digest"
    assert alerts[0].severity == "digest"
    assert "2" in alerts[0].title
    assert "401" in alerts[0].payload_json and "402" in alerts[0].payload_json
    assert service.flush_watch_digest() == 0
    assert bus.events[-1][0] == "alert.created"


def test_digest_not_flushed_before_window_ends() -> None:
    service, clock, _ = _service(MONDAY_10AM)
    service.on_news_batch([{"id": 401, "title": "智谱发布新一代大模型", "summary": None, "source_name": "s", "market": "cn"}])

    clock.now += timedelta(minutes=10)
    assert service.flush_watch_digest() == 0


# ---------------------------------------------------------------- 静默时段


def test_quiet_hours_record_overnight_alert_visible_next_morning() -> None:
    service, _, bus = _service(MONDAY_23PM)

    payload = {"id": 501, "title": "寒武纪发布公告", "summary": None, "source_name": "s", "market": "cn"}
    assert service.on_news_batch([payload]) == 1

    alert = _alerts()[0]
    assert alert.overnight is True
    # 北京时间次日 08:00 = UTC 00:00
    assert alert.visible_at.replace(tzinfo=UTC) == datetime(2026, 11, 3, 0, 0, tzinfo=UTC)
    assert bus.events == []


def test_quiet_window_after_midnight_becomes_visible_same_morning() -> None:
    early = datetime(2026, 11, 2, 19, 30, tzinfo=UTC)  # 北京时间 11-03 03:30
    service, _, _ = _service(early)

    service.on_news_batch([{"id": 601, "title": "东山精密公告", "summary": None, "source_name": "s", "market": "cn"}])

    assert _alerts()[0].visible_at.replace(tzinfo=UTC) == datetime(2026, 11, 3, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------- 评审修复


def test_digest_hit_filed_after_concurrent_flush_is_not_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    """命中在"读时钟"与"写入窗口"之间，另一线程（行情回调）恰好把旧窗口落库：新命中不能丢。"""
    window_end = datetime(2026, 11, 2, 2, 30, tzinfo=UTC)
    service, clock, _ = _service(window_end - timedelta(minutes=20))
    service.on_news_batch([{"id": 701, "title": "智谱发布新模型", "summary": None, "source_name": "s", "market": "cn"}])

    clock.now = window_end - timedelta(milliseconds=1)
    original = AlertService._load_rule_mentions

    def load_then_concurrent_flush(session, news_ids, by_symbol):
        # 模拟批处理查库期间，时钟越过窗口边界，行情线程触发了一次 flush。
        clock.now = window_end + timedelta(milliseconds=4)
        service.flush_watch_digest()
        return original(session, news_ids, by_symbol)

    monkeypatch.setattr(AlertService, "_load_rule_mentions", staticmethod(load_then_concurrent_flush))
    service.on_news_batch([{"id": 702, "title": "智谱获得新融资", "summary": None, "source_name": "s", "market": "cn"}])
    monkeypatch.setattr(AlertService, "_load_rule_mentions", staticmethod(original))

    clock.now = window_end + timedelta(minutes=31)
    service.flush_watch_digest()

    payloads = " ".join(alert.payload_json for alert in _alerts())
    assert "701" in payloads
    assert "702" in payloads


def test_digest_write_failure_keeps_hits_and_holding_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    service, clock, _ = _service(MONDAY_10AM)
    service.on_news_batch([{"id": 801, "title": "智谱发布新模型", "summary": None, "source_name": "s", "market": "cn"}])
    clock.now += timedelta(minutes=31)

    original = AlertService._create_digest_alert
    calls = {"n": 0}

    def flaky(self, repo, window_start, group, hits, now):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database is locked")
        return original(self, repo, window_start, group, hits, now)

    monkeypatch.setattr(AlertService, "_create_digest_alert", flaky)

    # 批处理开头的 flush 失败，不能连带吞掉本批持仓新闻提醒。
    created = service.on_news_batch(
        [{"id": 802, "title": "东山精密获大单", "summary": None, "source_name": "s", "market": "cn"}]
    )
    assert created == 1

    # 失败的窗口放回缓冲，下一次 flush 写入。
    assert service.flush_watch_digest() == 1
    kinds = sorted(alert.kind for alert in _alerts())
    assert kinds == ["holding_news", "watch_news_digest"]


def test_short_us_ticker_needs_explicit_marker() -> None:
    with SessionLocal() as session:
        session.add(WatchlistItem(symbol="AI", market="us", display_name="C3.ai", position_size=10, average_cost=20))
        session.commit()
    service, _, _ = _service(MONDAY_10AM)

    created = service.on_news_batch(
        [
            {"id": 901, "title": "AI芯片龙头大涨", "summary": None, "source_name": "s", "market": "cn"},
            {"id": 902, "title": "$AI jumps after earnings", "summary": None, "source_name": "s", "market": "us"},
        ]
    )

    assert created == 1
    alert = _alerts()[0]
    assert alert.symbol == "AI"
    assert "902" in alert.payload_json


def test_queue_worker_cycle_flushes_watch_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    """多进程形态下合并窗口在 pipeline worker 进程里：worker 每个周期都要推进 flush。"""
    from app.workers import queue_worker as queue_worker_module

    calls: list[str] = []

    class _Alerts:
        def flush_watch_digest(self) -> int:
            calls.append("flush")
            return 0

        def sweep_deferred(self) -> int:
            calls.append("sweep")
            return 0

    monkeypatch.setattr(queue_worker_module, "get_alert_service", lambda: _Alerts())
    worker = queue_worker_module.BackgroundQueueWorker(
        session_factory=SessionLocal,
        fallback_scan_interval_seconds=3600.0,
        inflight=queue_worker_module.InflightLeaseRegistry(),
    )
    worker._next_fallback_scan_at = float("inf")

    assert worker.do_cycle() == 0
    assert calls == ["flush", "sweep"]
    # AI 兜底扫描按 30 秒节流，不必每个周期都查库
    worker.do_cycle()
    assert calls == ["flush", "sweep", "flush"]
