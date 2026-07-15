"""告警治理层测试：免打扰时段 / 分级 / 去重窗口 / 合并摘要。

所有用例均注入固定时钟，且发送端一律用 MagicMock，绝不真发飞书 / 联网。
默认（不配置治理）行为在 test_feishu_notify.py 已覆盖，本文件只验证开启治理后的新行为。
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.feishu_notify_config import FeishuNotifyConfig
from app.models.notification_job import NotificationJob
from app.services.notification_service import NotificationService

client = TestClient(app)

VALID_CONFIG = {
    "app_id": "cli_test123",
    "app_secret": "secret_abc",
    "target_type": "chat",
    "target_id": "oc_test_chat_id",
    "news_enabled": False,
    "alert_enabled": True,
    "analysis_enabled": False,
    "news_batch_interval_minutes": 30,
    "is_active": True,
}


@pytest.fixture(autouse=True)
def _clean_state():
    with SessionLocal() as session:
        session.query(NotificationJob).delete()
        session.query(FeishuNotifyConfig).delete()
        session.commit()
    yield


def _create_config(**overrides):
    payload = dict(VALID_CONFIG)
    payload.update(overrides)
    resp = client.post("/api/notify/feishu/config", json=payload)
    assert resp.status_code == 200
    return resp.json()


def _load_jobs(event_type: str | None = None):
    with SessionLocal() as session:
        query = session.query(NotificationJob).order_by(NotificationJob.id.asc())
        jobs = query.all()
    if event_type is not None:
        return [job for job in jobs if job.event_type == event_type]
    return jobs


def _fixed_clock(now: datetime):
    return lambda: now


def _as_utc(value: datetime) -> datetime:
    # 原生 ORM 读回的 DateTime 可能是 naive，补上 UTC 便于比较。
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _make_service(now: datetime, **governance) -> NotificationService:
    service = NotificationService()
    service._now_provider = _fixed_clock(now)
    if governance:
        service.configure_governance(**governance)
    return service


def _mock_sender():
    sender = MagicMock()
    sender.send_card.return_value = {"code": 0}
    return sender


# ---------------------------------------------------------------------------
# 免打扰时段（Quiet Hours）
# ---------------------------------------------------------------------------
def test_quiet_hours_suppress_low_severity_but_deliver_critical():
    _create_config(alert_enabled=True)
    # Asia/Shanghai = UTC+8。UTC 15:00 => 本地 23:00，落在 22:00-07:00 免打扰区间内。
    now = datetime(2026, 7, 13, 15, 0, tzinfo=UTC)
    service = _make_service(
        now,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
        quiet_hours_tz="Asia/Shanghai",
        critical_change_percent=8.0,
    )

    # 普通异动（3.5% < 8% 阈值）=> normal，免打扰内应被暂缓。
    service.on_watchlist_alert({
        "symbol": "NORMAL.HK",
        "display_name": "Normal",
        "price": 100.0,
        "change_percent": 3.5,
        "alert_threshold": 3.0,
    })
    # 极端异动（9% >= 8% 阈值）=> critical，免打扰内仍应发出。
    service.on_watchlist_alert({
        "symbol": "CRIT.HK",
        "display_name": "Critical",
        "price": 50.0,
        "change_percent": 9.0,
        "alert_threshold": 3.0,
    })

    sender = _mock_sender()
    with patch("app.services.notification_service.get_shared_feishu_sender", return_value=sender):
        service._delivery_tick(now=now)

    normal_job = next(j for j in _load_jobs("watchlist_alert") if json.loads(j.payload_json)["symbol"] == "NORMAL.HK")
    crit_job = next(j for j in _load_jobs("watchlist_alert") if json.loads(j.payload_json)["symbol"] == "CRIT.HK")

    # 普通异动被暂缓：仍 pending，未发送，next_retry_at 顺延到免打扰结束之后。
    assert normal_job.status == "pending"
    assert normal_job.sent_at is None
    assert normal_job.next_retry_at is not None
    assert _as_utc(normal_job.next_retry_at) > now

    # 极端异动照常发出。
    assert crit_job.status == "sent"
    sender.send_card.assert_called_once()


def test_quiet_hours_disabled_by_default_delivers_everything():
    _create_config(alert_enabled=True)
    now = datetime(2026, 7, 13, 15, 0, tzinfo=UTC)
    # 不配置 quiet hours（默认关闭）=> 普通异动照发。
    service = _make_service(now, critical_change_percent=8.0)
    service.on_watchlist_alert({
        "symbol": "NORMAL.HK",
        "display_name": "Normal",
        "price": 100.0,
        "change_percent": 3.5,
        "alert_threshold": 3.0,
    })

    sender = _mock_sender()
    with patch("app.services.notification_service.get_shared_feishu_sender", return_value=sender):
        service._delivery_tick(now=now)

    job = _load_jobs("watchlist_alert")[0]
    assert job.status == "sent"
    sender.send_card.assert_called_once()


# ---------------------------------------------------------------------------
# 去重窗口（同 symbol 同事件 N 分钟内只发一次）
# ---------------------------------------------------------------------------
def test_dedupe_window_suppresses_repeat_within_window():
    _create_config(alert_enabled=True)
    t0 = datetime(2026, 7, 13, 2, 0, tzinfo=UTC)
    service = _make_service(
        t0,
        dedupe_window_minutes=10,
        critical_change_percent=100.0,  # 避免被判为 critical 走加急通道
    )

    payload = {
        "symbol": "0700.HK",
        "display_name": "Tencent",
        "price": 332.4,
        "change_percent": 3.33,
        "alert_threshold": 3.0,
    }
    # 首次越界 => 入队 1 条。
    service.on_watchlist_alert(payload)
    # 回落清 latch，再次越界（仍在 10 分钟窗口内）=> 被窗口抑制。
    service.on_watchlist_alert({**payload, "change_percent": 0.4})
    service.on_watchlist_alert({**payload, "change_percent": 3.88})

    assert len(_load_jobs("watchlist_alert")) == 1

    # 时钟推进到窗口外，再次越界 => 允许入队第 2 条。
    service._now_provider = _fixed_clock(t0 + timedelta(minutes=11))
    service.on_watchlist_alert({**payload, "change_percent": 0.4})
    service.on_watchlist_alert({**payload, "change_percent": 3.99})

    assert len(_load_jobs("watchlist_alert")) == 2


# ---------------------------------------------------------------------------
# 合并摘要（Digest）
# ---------------------------------------------------------------------------
def test_multiple_alerts_merge_into_single_digest_card():
    _create_config(alert_enabled=True)
    t0 = datetime(2026, 7, 13, 2, 0, tzinfo=UTC)
    service = _make_service(
        t0,
        digest_window_minutes=5,
        digest_threshold=2,
        critical_change_percent=100.0,  # 全部判为 normal，进入合并通道
    )

    for symbol in ("AAA.HK", "BBB.HK", "CCC.HK"):
        service.on_watchlist_alert({
            "symbol": symbol,
            "display_name": symbol,
            "price": 10.0,
            "change_percent": 3.5,
            "alert_threshold": 3.0,
        })

    # 开启合并后，个股告警被暂存（next_retry_at 顺延一个合并窗口），不会立即单发。
    held = _load_jobs("watchlist_alert")
    assert len(held) == 3
    assert all(j.status == "pending" and j.next_retry_at is not None for j in held)

    # 窗口结束后派发：三条合并为一张摘要卡片。
    sender = _mock_sender()
    with patch("app.services.notification_service.get_shared_feishu_sender", return_value=sender):
        service._delivery_tick(now=t0 + timedelta(minutes=6))

    digests = _load_jobs("alert_digest")
    assert len(digests) == 1
    assert digests[0].status == "sent"
    # 源告警被消费（标记 sent），不再单独发送。
    assert all(j.status == "sent" for j in _load_jobs("watchlist_alert"))
    # 只发了一张卡片。
    sender.send_card.assert_called_once()

    sent_card = sender.send_card.call_args.kwargs["card"]
    assert "3" in sent_card["header"]["title"]["content"]


def test_digest_disabled_by_default_delivers_individually():
    _create_config(alert_enabled=True)
    t0 = datetime(2026, 7, 13, 2, 0, tzinfo=UTC)
    # 不配置 digest（默认关闭）=> 逐条发送。
    service = _make_service(t0, critical_change_percent=100.0)

    for symbol in ("AAA.HK", "BBB.HK"):
        service.on_watchlist_alert({
            "symbol": symbol,
            "display_name": symbol,
            "price": 10.0,
            "change_percent": 3.5,
            "alert_threshold": 3.0,
        })

    sender = _mock_sender()
    with patch("app.services.notification_service.get_shared_feishu_sender", return_value=sender):
        service._delivery_tick(now=t0)

    assert _load_jobs("alert_digest") == []
    assert all(j.status == "sent" for j in _load_jobs("watchlist_alert"))
    assert sender.send_card.call_count == 2


# ---------------------------------------------------------------------------
# 卡片构造
# ---------------------------------------------------------------------------
def test_build_alert_digest_card_renders_all_items():
    from app.services.feishu_client import build_alert_digest_card

    card = build_alert_digest_card([
        {"symbol": "AAA.HK", "display_name": "AAA", "change_percent": 3.5, "price": 10.0, "alert_threshold": 3.0},
        {"symbol": "BBB.HK", "display_name": "BBB", "change_percent": -4.2, "price": 20.0, "alert_threshold": 3.0},
    ])
    assert "2" in card["header"]["title"]["content"]
    body = json.dumps(card, ensure_ascii=False)
    assert "AAA" in body and "BBB" in body


# ---------------------------------------------------------------------------
# 严重度分级
# ---------------------------------------------------------------------------
def test_severity_classification():
    service = NotificationService()
    service.configure_governance(critical_change_percent=8.0)

    critical = service._classify_severity("watchlist_alert", {"change_percent": 9.5, "alert_threshold": 3.0})
    normal = service._classify_severity("watchlist_alert", {"change_percent": 3.5, "alert_threshold": 3.0})
    low = service._classify_severity("news_batch", {})

    assert critical == "critical"
    assert normal == "normal"
    assert low == "low"
