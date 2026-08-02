"""POST /api/logs/frontend（前端错误日志上报）的行为测试。"""
from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.api.routes import logs as logs_module
from app.core.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    logs_module._accepted_at.clear()
    yield
    logs_module._accepted_at.clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_ingest_writes_to_frontend_logger(client, caplog):
    with caplog.at_level(logging.WARNING, logger="frontend"):
        response = client.post(
            "/api/logs/frontend",
            json={
                "entries": [
                    {
                        "level": "error",
                        "message": "Failed to load stats",
                        "stack": "TypeError: x is undefined\n  at load()",
                        "url": "http://localhost:5173/settings/llm",
                        "ts": "2026-08-02T10:00:00Z",
                        "context": {"view": "LlmSettingsView"},
                    },
                    {"level": "warn", "message": "slow route render"},
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"accepted": 2, "dropped": 0}
    records = [r for r in caplog.records if r.name == "frontend"]
    assert len(records) == 2
    error_record = records[0]
    assert error_record.levelno == logging.ERROR
    assert "Failed to load stats" in error_record.getMessage()
    assert "url=http://localhost:5173/settings/llm" in error_record.getMessage()
    assert "TypeError: x is undefined" in error_record.getMessage()
    assert records[1].levelno == logging.WARNING


def test_oversized_batch_is_rejected(client):
    entries = [{"level": "error", "message": f"e{i}"} for i in range(21)]
    response = client.post("/api/logs/frontend", json={"entries": entries})
    assert response.status_code == 413


def test_message_is_truncated(client, caplog):
    long_message = "x" * 5000
    with caplog.at_level(logging.ERROR, logger="frontend"):
        response = client.post(
            "/api/logs/frontend",
            json={"entries": [{"level": "error", "message": long_message}]},
        )

    assert response.status_code == 200
    message = [r for r in caplog.records if r.name == "frontend"][0].getMessage()
    assert "…(truncated)" in message
    assert len(message) < 3000


def test_rate_limit_drops_excess_silently(client, caplog):
    # 预填满窗口只剩 1 个配额，验证超额条目静默丢弃且仍返回 200。
    import time as time_module

    now = time_module.monotonic()
    settings = get_settings()
    for _ in range(settings.frontend_log_rate_limit_per_minute - 1):
        logs_module._accepted_at.append(now)

    with caplog.at_level(logging.ERROR, logger="frontend"):
        response = client.post(
            "/api/logs/frontend",
            json={
                "entries": [
                    {"level": "error", "message": "kept"},
                    {"level": "error", "message": "dropped"},
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "dropped": 1}
    messages = [r.getMessage() for r in caplog.records if r.name == "frontend"]
    assert any("kept" in m for m in messages)
    assert not any("dropped" in m for m in messages)


def test_invalid_level_is_rejected(client):
    response = client.post(
        "/api/logs/frontend",
        json={"entries": [{"level": "info", "message": "not allowed"}]},
    )
    assert response.status_code == 422
