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
        session.commit()
    yield


def _create_config():
    resp = client.post("/api/notify/feishu/config", json=VALID_CONFIG)
    assert resp.status_code == 200
    return resp.json()


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
    with patch("app.api.routes.notify.FeishuClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.send_test.return_value = {"code": 0}
        mock_cls.return_value = mock_client

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

    service = NotificationService()

    with patch.object(service, "_load_config") as mock_config:
        config = MagicMock()
        config.news_enabled = True
        config.news_keywords = "tencent,nvidia"
        mock_config.return_value = config

        service.on_news_created({"title": "Tencent AI launch", "summary": "test"})
        assert len(service._news_buffer) == 1

        service.on_news_created({"title": "Apple supply update", "summary": "chip demand"})
        assert len(service._news_buffer) == 1
