import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.feishu_notify_config import FeishuNotifyConfig

client = TestClient(app)

VALID_CONFIG = {
    "app_id": "cli_test123",
    "app_secret": "secret_abc",
    "target_type": "chat",
    "target_id": "oc_test_chat_id",
    "news_enabled": True,
    "alert_enabled": True,
    "analysis_enabled": False,
    "news_batch_interval_minutes": 30,
    "is_active": True,
}


@pytest.fixture(autouse=True)
def _clean_feishu_config():
    with SessionLocal() as session:
        session.query(FeishuNotifyConfig).delete()
        try:
            from app.models.notification_job import NotificationJob
        except Exception:
            NotificationJob = None
        if NotificationJob is not None:
            session.query(NotificationJob).delete()
        session.commit()
    yield


def _create_config(**overrides):
    payload = dict(VALID_CONFIG)
    payload.update(overrides)
    resp = client.post("/api/notify/feishu/config", json=payload)
    assert resp.status_code == 200
    return resp.json()


def _load_notification_jobs():
    from app.models.notification_job import NotificationJob

    with SessionLocal() as session:
        return session.query(NotificationJob).order_by(NotificationJob.id.asc()).all()


def _job_payload(job) -> dict:
    payload = job.payload_json
    if isinstance(payload, str):
        return json.loads(payload)
    return payload


def _set_all_notification_job_created_at(created_at: datetime) -> None:
    from sqlalchemy import text

    with SessionLocal() as session:
        session.execute(text("UPDATE notification_job SET created_at = :created_at"), {"created_at": created_at})
        session.commit()


def test_get_feishu_config_not_configured():
    resp = client.get("/api/notify/feishu/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["app_id"] is None


def test_upsert_feishu_config_requires_secret_on_first():
    resp = client.post(
        "/api/notify/feishu/config",
        json={"app_id": "cli_test123", "target_type": "chat", "target_id": "oc_test_chat_id"},
    )
    assert resp.status_code == 400
    assert "app_secret" in resp.json()["detail"].lower()


def test_upsert_feishu_config_success():
    data = _create_config()
    assert data["configured"] is True
    assert data["app_id"] == "cli_test123"
    assert data["app_secret_set"] is True
    assert data["target_type"] == "chat"
    assert data["target_id"] == "oc_test_chat_id"
    assert data["news_enabled"] is True
    assert data["analysis_enabled"] is False
    assert data["news_batch_interval_minutes"] == 30


def test_get_feishu_config_after_save():
    _create_config()
    resp = client.get("/api/notify/feishu/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["app_id"] == "cli_test123"


def test_upsert_feishu_config_preserves_secret():
    _create_config()
    resp = client.post(
        "/api/notify/feishu/config",
        json={
            "app_id": "cli_test123",
            "target_type": "user",
            "target_id": "ou_test_user_id",
            "news_enabled": False,
            "alert_enabled": True,
            "analysis_enabled": True,
            "news_batch_interval_minutes": 60,
            "is_active": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["app_secret_set"] is True
    assert data["target_type"] == "user"
    assert data["target_id"] == "ou_test_user_id"
    assert data["news_enabled"] is False


def test_test_feishu_notification():
    _create_config()
    with patch("app.api.routes.notify.get_shared_feishu_sender") as mock_sender_factory:
        mock_client = MagicMock()
        mock_client.send_test.return_value = {"code": 0}
        mock_sender_factory.return_value = mock_client

        resp = client.post("/api/notify/feishu/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "成功" in data["message"]
        mock_client.send_test.assert_called_once()


def test_feishu_client_build_cards():
    from app.services.feishu_client import (
        build_alert_card,
        build_analysis_card,
        build_news_batch_card,
        build_test_card,
    )

    test_card = build_test_card()
    assert test_card["header"]["title"]["content"] == "✅ News Caught 连通性测试"

    news_card = build_news_batch_card([
        {"title": "Test News", "source_name": "Reuters", "market": "us"},
        {"title": "Another News", "source_name": "Bloomberg", "market": "hk"},
    ])
    assert "2 条" in news_card["header"]["title"]["content"]

    alert_card = build_alert_card(
        symbol="AAPL", display_name="Apple",
        price=215.32, change_percent=-3.5, threshold=2.0,
    )
    assert "Apple" in alert_card["header"]["title"]["content"]

    analysis_card = build_analysis_card(
        news_title="Tencent AI expansion",
        top_pick={"symbol": "0700.HK", "company_name": "Tencent", "reason": "Direct AI exposure"},
        candidates=[],
        summary="Tencent is the main read-through.",
        risk_notes="Single source risk.",
    )
    assert "LLM" in analysis_card["header"]["title"]["content"]


def test_notification_service_news_filter():
    from app.services.notification_service import NotificationService

    _create_config(news_enabled=True, news_keywords="tencent,nvidia")
    service = NotificationService()
    service.on_news_created({"title": "Tencent AI launch", "summary": "test"})
    service.on_news_created({"title": "Apple supply update", "summary": "chip demand"})

    jobs = _load_notification_jobs()
    source_jobs = [job for job in jobs if job.event_type == "news_source_event"]
    assert len(source_jobs) == 1
    assert _job_payload(source_jobs[0])["title"] == "Tencent AI launch"


def test_analysis_completion_enqueues_job_instead_of_sending_inline():
    from app.services.notification_service import NotificationService

    _create_config(analysis_enabled=True)
    service = NotificationService()
    service._send = MagicMock(return_value=True)

    service.on_analysis_completed({
        "news_title": "Tencent AI expansion",
        "top_pick": {"symbol": "0700.HK", "company_name": "Tencent", "reason": "Direct AI exposure"},
        "candidates": [],
        "summary": "Tencent is the main read-through.",
        "risk_notes": "Single source risk.",
    })

    jobs = _load_notification_jobs()
    assert len(jobs) == 1
    assert jobs[0].event_type == "analysis_result"
    assert jobs[0].status == "pending"
    assert _job_payload(jobs[0])["news_title"] == "Tencent AI expansion"


def test_watchlist_alert_enqueues_once_per_threshold_crossing():
    from app.services.notification_service import NotificationService

    _create_config(alert_enabled=True)
    service = NotificationService()
    service._send = MagicMock(return_value=True)

    payload = {
        "symbol": "0700.HK",
        "display_name": "Tencent",
        "price": 332.4,
        "change_percent": 3.33,
        "alert_threshold": 3.0,
    }

    service.on_watchlist_alert(payload)
    service.on_watchlist_alert(payload)
    service.on_watchlist_alert({**payload, "change_percent": 0.4})
    service.on_watchlist_alert({**payload, "change_percent": 3.88, "price": 334.2})

    jobs = _load_notification_jobs()
    alert_jobs = [job for job in jobs if job.event_type == "watchlist_alert"]
    assert len(alert_jobs) == 2


def test_watchlist_permanent_failure_releases_latch_for_reenqueue():
    from app.services.feishu_client import FeishuClientError
    from app.services.notification_service import NotificationService

    _create_config(alert_enabled=True)
    service = NotificationService()
    payload = {
        "symbol": "0700.HK",
        "display_name": "Tencent",
        "price": 332.4,
        "change_percent": 3.33,
        "alert_threshold": 3.0,
    }

    service.on_watchlist_alert(payload)
    failing_sender = MagicMock()
    failing_sender.send_card.side_effect = FeishuClientError("bad config", retryable=False)
    with patch("app.services.notification_service.get_shared_feishu_sender", return_value=failing_sender):
        service._delivery_tick(now=datetime.now(timezone.utc))

    service.on_watchlist_alert(payload)

    jobs = _load_notification_jobs()
    alert_jobs = [job for job in jobs if job.event_type == "watchlist_alert"]
    assert len(alert_jobs) == 2


def test_news_created_persists_source_events_instead_of_memory_buffer():
    from app.services.notification_service import NotificationService

    _create_config(news_enabled=True, news_batch_interval_minutes=1)
    service = NotificationService()

    service.on_news_created({
        "title": "Tencent AI launch",
        "summary": "AI workflow tooling",
        "source_name": "Reuters",
        "market": "hk",
    })
    service.on_news_created({
        "title": "Nvidia enterprise expansion",
        "summary": "GPU cluster rollout",
        "source_name": "Bloomberg",
        "market": "us",
    })

    jobs = _load_notification_jobs()
    source_jobs = [job for job in jobs if job.event_type == "news_source_event"]
    assert len(source_jobs) == 2
    if hasattr(service, "_news_buffer"):
        assert service._news_buffer == []


def test_news_events_batch_into_single_card_when_window_is_due():
    from app.services.notification_service import NotificationService

    _create_config(news_enabled=True, news_batch_interval_minutes=1)
    service = NotificationService()
    service.on_news_created({
        "title": "Tencent AI launch",
        "summary": "AI workflow tooling",
        "source_name": "Reuters",
        "market": "hk",
    })
    service.on_news_created({
        "title": "Nvidia enterprise expansion",
        "summary": "GPU cluster rollout",
        "source_name": "Bloomberg",
        "market": "us",
    })
    _set_all_notification_job_created_at(datetime.now(timezone.utc) - timedelta(minutes=2))

    mock_sender = MagicMock()
    mock_sender.send_card.return_value = {"code": 0}
    with patch("app.services.notification_service.get_shared_feishu_sender", return_value=mock_sender):
        service._delivery_tick(now=datetime.now(timezone.utc))

    jobs = _load_notification_jobs()
    batch_jobs = [job for job in jobs if job.event_type == "news_batch"]
    assert len(batch_jobs) == 1
    assert batch_jobs[0].status == "sent"
    mock_sender.send_card.assert_called_once()


def test_disabling_news_discards_pending_source_events():
    from app.services.notification_service import NotificationService

    _create_config(news_enabled=True, news_batch_interval_minutes=1)
    service = NotificationService()
    service.on_news_created({
        "title": "Tencent AI launch",
        "summary": "AI workflow tooling",
        "source_name": "Reuters",
        "market": "hk",
    })

    _create_config(news_enabled=False, news_batch_interval_minutes=1)
    service._delivery_tick(now=datetime.now(timezone.utc))

    assert _load_notification_jobs() == []


def test_delivery_tick_retries_retryable_failures_and_marks_sent_after_success():
    from app.services.feishu_client import FeishuClientError
    from app.services.notification_service import NotificationService

    _create_config(analysis_enabled=True)
    service = NotificationService()
    service.on_analysis_completed({
        "news_title": "Tencent AI expansion",
        "top_pick": {"symbol": "0700.HK", "company_name": "Tencent", "reason": "Direct AI exposure"},
        "candidates": [],
        "summary": "Tencent is the main read-through.",
        "risk_notes": "Single source risk.",
    })

    first_now = datetime.now(timezone.utc)
    retrying_sender = MagicMock()
    retrying_sender.send_card.side_effect = FeishuClientError("temporary timeout", retryable=True)
    with patch("app.services.notification_service.get_shared_feishu_sender", return_value=retrying_sender):
        service._delivery_tick(now=first_now)

    jobs_after_failure = _load_notification_jobs()
    analysis_job = next(job for job in jobs_after_failure if job.event_type == "analysis_result")
    assert analysis_job.status == "pending"
    assert analysis_job.last_error == "temporary timeout"
    assert analysis_job.next_retry_at is not None

    success_sender = MagicMock()
    success_sender.send_card.return_value = {"code": 0}
    with patch("app.services.notification_service.get_shared_feishu_sender", return_value=success_sender):
        service._delivery_tick(now=analysis_job.next_retry_at + timedelta(seconds=1))

    jobs_after_success = _load_notification_jobs()
    sent_job = next(job for job in jobs_after_success if job.event_type == "analysis_result")
    assert sent_job.status == "sent"
    assert sent_job.sent_at is not None


def test_notification_service_start_is_idempotent_for_delivery_thread():
    from app.services.notification_service import NotificationService

    service = NotificationService(poll_interval_seconds=1)
    service.start()
    first_thread = service._delivery_thread
    service.start()

    assert service._delivery_thread is first_thread
    assert first_thread is not None
    assert first_thread.is_alive()

    service.stop()
