"""P3：AI 判断接管新闻提醒（AI 为主，关键词兜底）。

- AI 模式下 ``on_news_batch`` 不再按关键词发提醒，由漏斗在 L2 完成后调 ``on_news_impacts``；
- 持仓股：利多/利空且强度 ≥ 中 → 立即提醒（每只每天上限，超出进合并窗口）；
- 只关注的股票同条件 → 合并窗口；关注板块 → 板块合并；自选外"利多·强" → 新机会合并；
- 海外 + 重大 → 立即提醒（每天上限）；
- AI 不在线时 ``on_news_batch`` 照旧走关键词；漏斗最终失败的新闻调 ``on_news_keyword_fallback`` 补发。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.db.session import SessionLocal
from app.models.alert import Alert
from app.models.sector import FocusSectorOverride, StockSector
from app.models.watchlist_item import WatchlistItem
from app.services.alert_service import AlertService

MONDAY_10AM = datetime(2026, 11, 2, 2, 0, tzinfo=UTC)
MONDAY_23PM = datetime(2026, 11, 2, 15, 0, tzinfo=UTC)


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
    def wipe(session) -> None:
        session.query(Alert).delete()
        session.query(StockSector).delete()
        session.query(FocusSectorOverride).delete()
        session.query(WatchlistItem).delete()

    with SessionLocal() as session:
        wipe(session)
        session.add_all(
            [
                WatchlistItem(symbol="688256.SH", market="cn", display_name="寒武纪", position_size=100, average_cost=1100),
                WatchlistItem(symbol="HK2513", market="hk", display_name="智谱", position_size=None),
                StockSector(symbol="688256.SH", sector="半导体", source="ai"),
            ]
        )
        session.commit()
    yield
    with SessionLocal() as session:
        wipe(session)
        session.commit()


def _service(now: datetime, *, ai_mode: bool = True) -> tuple[AlertService, _Clock, _Bus]:
    clock = _Clock(now)
    bus = _Bus()
    service = AlertService(
        session_factory=SessionLocal,
        event_bus=bus,
        clock=clock,
        quiet_hours=("22:00", "08:00"),
        tz_name="Asia/Shanghai",
        watch_digest_minutes=30,
        ai_mode_checker=lambda: ai_mode,
        ai_stock_alert_daily_limit=2,
        ai_overseas_alert_daily_limit=1,
    )
    return service, clock, bus


def _alerts() -> list[Alert]:
    with SessionLocal() as session:
        return list(session.query(Alert).order_by(Alert.id))


def _news(news_id: int, title: str = "Nvidia beats", title_zh: str | None = "英伟达业绩超预期") -> dict:
    return {"id": news_id, "title": title, "title_zh": title_zh, "source_name": "Reuters", "market": "us"}


def _impact(name: str, code: str | None = None, *, target_type: str = "stock", direction: str = "bullish",
            strength: str = "strong", rationale: str = "理由") -> dict:
    return {"target_type": target_type, "code": code, "name": name, "direction": direction,
            "strength": strength, "rationale": rationale}


def test_ai_mode_skips_keyword_alerts() -> None:
    service, _, _ = _service(MONDAY_10AM, ai_mode=True)
    assert service.on_news_batch([{"id": 1, "title": "寒武纪发布新品", "source_name": "x"}]) == 0
    assert _alerts() == []

    keyword_service, _, _ = _service(MONDAY_10AM, ai_mode=False)
    assert keyword_service.on_news_batch([{"id": 1, "title": "寒武纪发布新品", "source_name": "x"}]) == 1


def test_keyword_fallback_always_uses_keyword_rules() -> None:
    service, _, _ = _service(MONDAY_10AM, ai_mode=True)
    assert service.on_news_keyword_fallback([{"id": 2, "title": "寒武纪发布新品", "source_name": "x"}]) == 1


def test_holding_impact_alerts_immediately_with_direction_and_view() -> None:
    service, _, bus = _service(MONDAY_10AM)
    created = service.on_news_impacts(
        _news(10), overseas=True, major=False, view="利好国产 AI 芯片",
        impacts=[_impact("寒武纪", "688256.SH", rationale="需求外溢")],
    )
    assert created == 1
    alert = _alerts()[0]
    assert alert.kind == "holding_news" and alert.symbol == "688256.SH"
    assert alert.title == "寒武纪：英伟达业绩超预期"
    assert "利多·强" in alert.body and "需求外溢" in alert.body and "利好国产 AI 芯片" in alert.body
    assert alert.dedupe_key == "news:10:688256.SH"
    assert [event for event, _ in bus.events] == ["alert.created"]


def test_weak_or_neutral_holding_impact_does_not_alert() -> None:
    service, clock, _ = _service(MONDAY_10AM)
    service.on_news_impacts(
        _news(11), overseas=False, major=False, view=None,
        impacts=[_impact("寒武纪", "688256.SH", strength="weak"), _impact("寒武纪", "688256.SH", direction="neutral")],
    )
    clock.now += timedelta(minutes=31)
    service.flush_watch_digest()
    assert _alerts() == []


def test_holding_daily_cap_overflows_into_digest() -> None:
    service, clock, _ = _service(MONDAY_10AM)
    for news_id in (21, 22, 23):
        service.on_news_impacts(_news(news_id), overseas=False, major=False, view=None,
                                impacts=[_impact("寒武纪", "688256.SH", direction="bearish", strength="medium")])
    assert [a.kind for a in _alerts()] == ["holding_news", "holding_news"]
    clock.now += timedelta(minutes=31)
    service.flush_watch_digest()
    digest = _alerts()[-1]
    assert digest.kind == "watch_news_digest" and "寒武纪" in digest.body


def test_watch_sector_and_opportunity_hits_are_digested_separately() -> None:
    service, clock, bus = _service(MONDAY_10AM)
    created = service.on_news_impacts(
        _news(30), overseas=False, major=False, view="v",
        impacts=[
            _impact("智谱", "02513", strength="medium"),
            _impact("半导体", target_type="sector", direction="bearish", strength="medium"),
            _impact("消费电子", target_type="sector", strength="strong"),  # 不是关注板块
            _impact("中际旭创", "300308.SZ"),  # 自选外 + 利多·强 → 新机会
            _impact("工业富联", "601138.SH", strength="medium"),  # 自选外但不够强
        ],
    )
    assert created == 0 and _alerts() == []
    clock.now += timedelta(minutes=31)
    assert service.flush_watch_digest() == 3
    by_kind = {alert.kind: alert for alert in _alerts()}
    assert set(by_kind) == {"watch_news_digest", "sector_news_digest", "opportunity_digest"}
    assert "智谱" in by_kind["watch_news_digest"].body
    assert "半导体" in by_kind["sector_news_digest"].title and "消费电子" not in by_kind["sector_news_digest"].body
    assert "中际旭创" in by_kind["opportunity_digest"].body and "工业富联" not in by_kind["opportunity_digest"].body
    assert all(alert.severity == "digest" for alert in by_kind.values())
    assert by_kind["opportunity_digest"].payload_json and '"news_id": 30' in by_kind["opportunity_digest"].payload_json


def test_overseas_major_alerts_immediately_with_daily_cap() -> None:
    service, _, _ = _service(MONDAY_10AM)
    assert service.on_news_impacts(_news(40), overseas=True, major=True, view="美联储意外降息", impacts=[]) == 1
    assert service.on_news_impacts(_news(41, title="Fed", title_zh="美联储"), overseas=True, major=True,
                                   view="v", impacts=[]) == 0  # 每天上限 1
    assert service.on_news_impacts(_news(42), overseas=False, major=True, view="v", impacts=[]) == 0  # 非海外
    alert = _alerts()[0]
    assert alert.kind == "overseas_major" and alert.title == "海外重大：英伟达业绩超预期"
    assert "美联储意外降息" in alert.body and alert.dedupe_key == "overseas:40"


def test_ai_alerts_respect_quiet_hours() -> None:
    service, _, bus = _service(MONDAY_23PM)
    service.on_news_impacts(_news(50), overseas=True, major=True, view="v",
                            impacts=[_impact("寒武纪", "688256.SH")])
    alerts = _alerts()
    assert len(alerts) == 2 and all(alert.overnight for alert in alerts)
    assert bus.events == []
