from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.main import app
from app.models.x_account import XAccount
from app.repositories.x_post_repository import XPostRepository
from app.services.grok_bridge_client import GrokBridgeClient, GrokBridgeError
from app.services.x_monitor import XMonitorService


def _test_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def test_grok_bridge_client_chat_success(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, path: str, json: dict[str, object]):
            assert path == "/chat"
            assert json["prompt"] == "hello"
            return httpx.Response(200, json={"status": "ok", "response": '[{"account_handle":"DeItaone"}]'})

    monkeypatch.setattr(
        "app.services.grok_bridge_client.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            grok_bridge_base_url="http://127.0.0.1:19998",
            grok_bridge_timeout_seconds=30.0,
        ),
    )
    monkeypatch.setattr("app.services.grok_bridge_client.httpx.Client", FakeClient)

    client = GrokBridgeClient()
    assert client.chat("hello") == '[{"account_handle":"DeItaone"}]'


def test_grok_bridge_client_chat_invalid_json(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, path: str, json: dict[str, object]):
            return httpx.Response(200, text="not-json")

    monkeypatch.setattr(
        "app.services.grok_bridge_client.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            grok_bridge_base_url="http://127.0.0.1:19998",
            grok_bridge_timeout_seconds=30.0,
        ),
    )
    monkeypatch.setattr("app.services.grok_bridge_client.httpx.Client", FakeClient)

    client = GrokBridgeClient()
    try:
        client.chat("hello")
    except GrokBridgeError as exc:
        assert "invalid json" in str(exc)
    else:
        raise AssertionError("expected GrokBridgeError")


def test_x_monitor_refresh_deduplicates_posts(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(
        '{"accounts":[{"handle":"DeItaone","display_name":"Delta One","market_focus":"us","is_active":true,"priority":100}]}',
        encoding="utf-8",
    )

    class FakeBridgeClient:
        configured = True

        def __init__(self) -> None:
            pass

        def chat(self, prompt: str) -> str:
            assert "@DeItaone" in prompt
            return """
            [
              {
                "account_handle": "DeItaone",
                "account_display_name": "Delta One",
                "post_text": "NVDA suppliers remain in focus",
                "posted_at": "2026-03-16T07:00:00Z",
                "url": "https://x.com/DeItaone/status/123",
                "symbols": ["NVDA"],
                "market": "us",
                "sentiment_label": "positive",
                "relevance_score": 0.91,
                "reason": "AI infra"
              }
            ]
            """

    monkeypatch.setattr(
        "app.services.x_monitor.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            x_monitor_accounts_file=str(accounts_file),
            grok_bridge_base_url="http://127.0.0.1:19998",
            grok_bridge_timeout_seconds=60.0,
        ),
    )
    monkeypatch.setattr("app.services.x_monitor.GrokBridgeClient", FakeBridgeClient)

    with _test_session() as session:
        service = XMonitorService(session)
        first = service.refresh()
        second = service.refresh()

        assert first.fetched_count == 1
        assert first.inserted_count == 1
        assert second.fetched_count == 1
        assert second.inserted_count == 0

        rows = service.posts.list_posts(account_handle="DeItaone", symbol="NVDA", market="us", query="suppliers", limit=10)
        assert len(rows) == 1
        post, account, symbols = rows[0]
        assert account.handle == "DeItaone"
        assert post.canonical_url == "https://x.com/DeItaone/status/123"
        assert symbols == ["NVDA"]


def test_x_posts_endpoint_returns_disabled_when_feature_is_off(monkeypatch) -> None:
    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def ensure_enabled(self) -> None:
            raise ValueError("x monitor is disabled")

    monkeypatch.setattr("app.api.routes.x_monitor.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.get("/api/x/posts")

    assert response.status_code == 503
    assert response.json()["detail"] == "x monitor is disabled"


def test_x_refresh_endpoint_returns_summary(monkeypatch) -> None:
    now = datetime(2026, 3, 16, 7, 0, tzinfo=timezone.utc)

    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def ensure_enabled(self) -> None:
            return None

        def refresh(self):
            return SimpleNamespace(
                started_at=now,
                finished_at=now,
                fetched_count=3,
                inserted_count=2,
                error=None,
                latency_ms=1234.0,
            )

    monkeypatch.setattr("app.api.routes.x_monitor.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.post("/api/x/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fetched_count"] == 3
    assert payload["inserted_count"] == 2
    assert payload["latency_ms"] == 1234.0


def test_x_health_endpoint_reports_bridge_state(monkeypatch) -> None:
    class FakeHealthRepo:
        def get_or_create(self, provider_name: str):
            assert provider_name == "grok-bridge"
            return SimpleNamespace(
                provider_name=provider_name,
                last_success_at=None,
                last_failure_at=None,
                consecutive_failures=0,
                total_fetches=0,
                total_failures=0,
                avg_latency_ms=None,
                last_error=None,
            )

    class FakeService:
        def __init__(self, session) -> None:
            self.session = session
            self.health_repo = FakeHealthRepo()

        def bridge_health(self):
            return True, "ok:grok.com"

    monkeypatch.setattr(
        "app.api.routes.health.get_settings",
        lambda: SimpleNamespace(x_monitor_enabled=True, grok_bridge_base_url="http://127.0.0.1:19998"),
    )
    monkeypatch.setattr("app.api.routes.health.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.get("/api/health/x")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["bridge_healthy"] is True
    assert payload["bridge_status"] == "ok:grok.com"
