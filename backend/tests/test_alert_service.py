"""站内提醒规则测试（聚焦改造 P2-T2）。

规则：
- 价格：仅持仓股（position_size > 0），|涨跌幅| >= 5%，只在该市场交易时段内触发；
  去重键用昨收价区分交易日（节假日行情不更新、昨收不变 → 不重复提醒）。
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


def test_holding_price_move_alerts_once_per_trading_day() -> None:
    service, clock, bus = _service(MONDAY_10AM)

    assert service.on_quotes([_quote("688256.SH", 6.1)]) == 1
    clock.now += timedelta(minutes=5)
    assert service.on_quotes([_quote("688256.SH", 7.0)]) == 0  # 同一交易日

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
    service, _, _ = _service(MONDAY_10AM)

    created = service.on_quotes(
        [
            _quote("002384.SZ", 4.99),  # 未到阈值
            _quote("688256.SH", -5.0),  # 跌 5% 触发
            _quote("HK2513", 9.0, market="hk"),  # 仅关注、无持仓：不做价格提醒
            _quote("600519.SH", 8.0),  # 不在自选
        ]
    )

    assert created == 1
    alert = _alerts()[0]
    assert alert.symbol == "688256.SH"
    assert "跌" in alert.title


def test_price_move_ignored_outside_trading_session() -> None:
    saturday = datetime(2026, 11, 7, 2, 0, tzinfo=UTC)
    service, _, _ = _service(saturday)

    assert service.on_quotes([_quote("688256.SH", 6.1)]) == 0
    assert _alerts() == []


def test_holiday_with_unchanged_previous_close_does_not_repeat() -> None:
    service, clock, _ = _service(MONDAY_10AM)
    service.on_quotes([_quote("688256.SH", 6.1, prev=100.0)])

    clock.now += timedelta(days=1)  # 周二若休市，行情仍是周一数据，昨收不变
    assert service.on_quotes([_quote("688256.SH", 6.1, prev=100.0)]) == 0

    clock.now += timedelta(days=1)  # 新交易日，昨收变了
    assert service.on_quotes([_quote("688256.SH", 5.5, prev=106.1)]) == 1


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
