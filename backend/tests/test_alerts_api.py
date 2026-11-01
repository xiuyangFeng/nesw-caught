"""站内提醒存储与接口测试（聚焦改造 P2-T1）。

覆盖：
- 按 dedupe_key 幂等写入（同一键第二次写入返回 None，不产生重复行）
- 可见性：visible_at 晚于当前时刻的提醒（隔夜提醒，次日 08:00 才可见）不出现在列表与未读数中
- 已读：单条已读、全部已读只影响已可见的提醒
- 路由：GET /api/alerts、GET /api/alerts/unread-count、POST /api/alerts/{id}/read、POST /api/alerts/read-all
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.routes import alerts as alerts_routes
from app.db.session import SessionLocal
from app.main import app
from app.models.alert import Alert
from app.repositories.alert_repository import AlertRepository

NOW = datetime(2026, 11, 2, 2, 0, tzinfo=UTC)  # 北京时间 10:00


@pytest.fixture(autouse=True)
def _clean_alerts():
    with SessionLocal() as session:
        session.query(Alert).delete()
        session.commit()
    yield
    with SessionLocal() as session:
        session.query(Alert).delete()
        session.commit()


def _create(repo: AlertRepository, key: str, *, visible_at: datetime = NOW, symbol: str | None = "002384.SZ", **extra):
    return repo.create_if_absent(
        kind=extra.pop("kind", "holding_price_move"),
        severity=extra.pop("severity", "immediate"),
        symbol=symbol,
        title=extra.pop("title", f"title {key}"),
        body=extra.pop("body", "body"),
        payload=extra.pop("payload", {"change_percent": 6.1}),
        dedupe_key=key,
        overnight=extra.pop("overnight", False),
        visible_at=visible_at,
        created_at=extra.pop("created_at", visible_at),
    )


def test_create_if_absent_is_idempotent_by_dedupe_key() -> None:
    with SessionLocal() as session:
        repo = AlertRepository(session)
        first = _create(repo, "price:002384.SZ:2026-11-02")
        second = _create(repo, "price:002384.SZ:2026-11-02")
        session.commit()

        assert first is not None
        assert second is None
        assert session.query(Alert).count() == 1


def test_overnight_alerts_hidden_until_visible_at() -> None:
    with SessionLocal() as session:
        repo = AlertRepository(session)
        _create(repo, "visible")
        _create(repo, "overnight", visible_at=NOW + timedelta(hours=1), overnight=True)
        session.commit()

        visible = repo.list_visible(now=NOW, unread_only=False, limit=50)
        assert [item.dedupe_key for item in visible] == ["visible"]
        assert repo.unread_count(now=NOW) == 1
        later = repo.list_visible(now=NOW + timedelta(hours=2), unread_only=False, limit=50)
        assert {item.dedupe_key for item in later} == {"visible", "overnight"}


def test_list_orders_newest_first_and_filters_unread() -> None:
    with SessionLocal() as session:
        repo = AlertRepository(session)
        older = _create(repo, "older", visible_at=NOW - timedelta(minutes=10))
        _create(repo, "newer", visible_at=NOW - timedelta(minutes=1))
        session.flush()
        repo.mark_read(older.id, now=NOW)
        session.commit()

        assert [a.dedupe_key for a in repo.list_visible(now=NOW, unread_only=False, limit=50)] == ["newer", "older"]
        assert [a.dedupe_key for a in repo.list_visible(now=NOW, unread_only=True, limit=50)] == ["newer"]


def test_mark_all_read_only_touches_visible_alerts() -> None:
    with SessionLocal() as session:
        repo = AlertRepository(session)
        _create(repo, "a")
        _create(repo, "b")
        _create(repo, "future", visible_at=NOW + timedelta(hours=1))
        session.commit()

        assert repo.mark_all_read(now=NOW) == 2
        session.commit()
        assert repo.unread_count(now=NOW + timedelta(hours=2)) == 1


def test_alert_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alerts_routes, "_now", lambda: NOW)
    with SessionLocal() as session:
        repo = AlertRepository(session)
        first = _create(repo, "price:002384.SZ:2026-11-02", title="东山精密 涨 6.10%")
        _create(repo, "hidden", visible_at=NOW + timedelta(hours=3), overnight=True)
        session.commit()
        first_id = first.id

    client = TestClient(app)

    listing = client.get("/api/alerts")
    assert listing.status_code == 200
    items = listing.json()
    assert [item["title"] for item in items] == ["东山精密 涨 6.10%"]
    assert items[0]["kind"] == "holding_price_move"
    assert items[0]["payload"] == {"change_percent": 6.1}
    assert items[0]["read_at"] is None

    assert client.get("/api/alerts/unread-count").json() == {"unread": 1}

    assert client.post(f"/api/alerts/{first_id}/read").status_code == 200
    assert client.get("/api/alerts/unread-count").json() == {"unread": 0}
    assert client.get("/api/alerts", params={"unread_only": True}).json() == []

    assert client.post("/api/alerts/999999/read").status_code == 404
    assert client.post("/api/alerts/read-all").json() == {"updated": 0}
