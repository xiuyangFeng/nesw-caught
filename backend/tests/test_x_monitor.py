from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.main import app
from app.services.x_monitor import _normalize_datetime
from app.services.x_monitor import XMonitorService


def _test_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


@pytest.fixture(autouse=True)
def reset_twitterapi_client_state():
    module = import_module("app.services.twitterapi_io_client")
    module.TwitterApiIoClient._last_request_started_at = None
    module.TwitterApiIoClient._last_probe_checked_at = None
    module.TwitterApiIoClient._last_probe_handle = None
    module.TwitterApiIoClient._last_probe_error = None
    yield
    module.TwitterApiIoClient._last_request_started_at = None
    module.TwitterApiIoClient._last_probe_checked_at = None
    module.TwitterApiIoClient._last_probe_handle = None
    module.TwitterApiIoClient._last_probe_error = None


def test_twitterapi_io_client_get_user_last_tweets_sends_api_key(monkeypatch) -> None:
    module = import_module("app.services.twitterapi_io_client")

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, path: str, headers: dict[str, str], params: dict[str, object]):
            assert "last_tweets" in path
            assert headers["X-API-Key"] == "test-key"
            assert params["userName"] == "DeItaone"
            assert params["includeReplies"] is False
            return httpx.Response(200, json={"data": {"tweets": [{"id": "190001"}]}})

    monkeypatch.setattr(
        "app.services.twitterapi_io_client.get_settings",
        lambda: SimpleNamespace(
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=12.5,
        ),
    )
    monkeypatch.setattr("app.services.twitterapi_io_client.httpx.Client", FakeClient)

    client = module.TwitterApiIoClient()
    assert client.get_user_last_tweets("DeItaone", limit=5) == [{"id": "190001"}]


def test_twitterapi_io_client_probe_account_uses_last_tweets_without_rate_limit(monkeypatch) -> None:
    module = import_module("app.services.twitterapi_io_client")
    module.TwitterApiIoClient._last_request_started_at = 100.0
    slept: list[float] = []

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, path: str, headers: dict[str, str], params: dict[str, object]):
            assert "last_tweets" in path
            assert params["userName"] == "MiniMax_AI"
            assert params["includeReplies"] is False
            assert params["limit"] == 1
            return httpx.Response(200, json={"data": {"tweets": [{"id": "190001"}]}})

    monkeypatch.setattr(
        "app.services.twitterapi_io_client.get_settings",
        lambda: SimpleNamespace(
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=12.5,
            twitterapi_io_min_interval_seconds=6.0,
        ),
    )
    monkeypatch.setattr("app.services.twitterapi_io_client.httpx.Client", FakeClient)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: slept.append(seconds))

    client = module.TwitterApiIoClient()
    client.probe_account("MiniMax_AI")

    assert slept == []


def test_twitterapi_io_client_raises_on_invalid_json(monkeypatch) -> None:
    module = import_module("app.services.twitterapi_io_client")

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, path: str, headers: dict[str, str], params: dict[str, object]):
            return httpx.Response(200, text="not-json")

    monkeypatch.setattr(
        "app.services.twitterapi_io_client.get_settings",
        lambda: SimpleNamespace(
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=12.5,
        ),
    )
    monkeypatch.setattr("app.services.twitterapi_io_client.httpx.Client", FakeClient)

    client = module.TwitterApiIoClient()
    try:
        client.get_user_last_tweets("DeItaone", limit=5)
    except module.TwitterApiIoError as exc:
        assert "invalid json" in str(exc).lower()
    else:
        raise AssertionError("expected TwitterApiIoError")


def test_twitterapi_io_client_waits_for_min_interval(monkeypatch) -> None:
    module = import_module("app.services.twitterapi_io_client")
    module.TwitterApiIoClient._last_request_started_at = None

    calls: list[dict[str, object]] = []
    slept: list[float] = []
    clock = {"value": 100.0}

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, path: str, headers: dict[str, str], params: dict[str, object]):
            calls.append({"path": path, "params": params})
            return httpx.Response(200, json={"data": {"tweets": [{"id": f'{len(calls)}'}]}})

    def fake_monotonic() -> float:
        return clock["value"]

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        clock["value"] += seconds

    monkeypatch.setattr(
        "app.services.twitterapi_io_client.get_settings",
        lambda: SimpleNamespace(
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=12.5,
            twitterapi_io_min_interval_seconds=6.0,
        ),
    )
    monkeypatch.setattr("app.services.twitterapi_io_client.httpx.Client", FakeClient)
    monkeypatch.setattr(module.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(module.time, "sleep", fake_sleep)

    client = module.TwitterApiIoClient()
    client.get_user_last_tweets("MiniMax_AI")
    client.get_user_last_tweets("MiniMax_AI")

    assert len(calls) == 2
    assert slept == [6.0]


def test_twitterapi_io_client_advanced_search_passes_limit(monkeypatch) -> None:
    module = import_module("app.services.twitterapi_io_client")

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, path: str, headers: dict[str, str], params: dict[str, object]):
            assert "advanced_search" in path
            assert params["query"] == "NVDA"
            assert params["queryType"] == "Latest"
            assert params["limit"] == 7
            return httpx.Response(200, json={"data": {"tweets": [{"id": "190001"}]}})

    monkeypatch.setattr(
        "app.services.twitterapi_io_client.get_settings",
        lambda: SimpleNamespace(
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=12.5,
            twitterapi_io_min_interval_seconds=0.0,
        ),
    )
    monkeypatch.setattr("app.services.twitterapi_io_client.httpx.Client", FakeClient)

    client = module.TwitterApiIoClient()
    assert client.advanced_search("NVDA", limit=7) == [{"id": "190001"}]


def test_x_monitor_refresh_deduplicates_posts_by_tweet_id(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(
        '{"accounts":[{"handle":"DeItaone","display_name":"Delta One","market_focus":"us","is_active":true,"priority":100}]}',
        encoding="utf-8",
    )

    class FakeTwitterApiIoClient:
        configured = True

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            assert handle == "DeItaone"
            assert limit >= 1
            return [
                {
                    "id": "190001",
                    "text": "NVDA suppliers remain in focus",
                    "createdAt": "2026-03-16T07:00:00Z",
                    "url": "https://x.com/DeItaone/status/190001",
                    "symbols": ["NVDA"],
                    "author": {
                        "userName": "DeItaone",
                        "name": "Delta One",
                    },
                }
            ]

    monkeypatch.setattr(
        "app.services.x_monitor.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            x_monitor_accounts_file=str(accounts_file),
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=30.0,
            x_monitor_refresh_cooldown_hours=0,
        ),
    )
    monkeypatch.setattr("app.services.x_monitor.TwitterApiIoClient", FakeTwitterApiIoClient)

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
        assert post.external_post_id == "190001"
        assert post.canonical_url == "https://x.com/DeItaone/status/190001"
        assert symbols == ["NVDA"]


def test_x_monitor_refresh_skips_when_cooldown_is_active(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(
        '{"accounts":[{"handle":"MiniMax_AI","display_name":"MiniMax AI","market_focus":"us","is_active":true,"priority":100}]}',
        encoding="utf-8",
    )
    now = datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc)
    recent_success = datetime(2026, 3, 19, 8, 0, tzinfo=timezone.utc)

    class FakeTwitterApiIoClient:
        configured = True

        def __init__(self) -> None:
            self.called = False

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            self.called = True
            raise AssertionError("cooldown should skip provider requests")

    monkeypatch.setattr(
        "app.services.x_monitor.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            x_monitor_accounts_file=str(accounts_file),
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=30.0,
            x_monitor_refresh_cooldown_hours=3,
        ),
    )
    monkeypatch.setattr("app.services.x_monitor.TwitterApiIoClient", FakeTwitterApiIoClient)
    monkeypatch.setattr("app.services.x_monitor._utc_now", lambda: now)

    with _test_session() as session:
        service = XMonitorService(session)
        health = service.health_repo.get_or_create("twitterapi.io")
        health.last_success_at = recent_success
        session.commit()

        summary = service.refresh()

        assert summary.fetched_count == 0
        assert summary.inserted_count == 0
        assert summary.skipped is True
        assert summary.skip_reason == "cooldown_active"
        assert summary.next_refresh_at == datetime(2026, 3, 19, 11, 0, tzinfo=timezone.utc)


def test_x_monitor_refresh_without_active_accounts_does_not_start_cooldown(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text('{"accounts":[]}', encoding="utf-8")
    now = datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc)

    class FakeTwitterApiIoClient:
        configured = True

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            raise AssertionError("no provider request expected when account list is empty")

    monkeypatch.setattr(
        "app.services.x_monitor.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            x_monitor_accounts_file=str(accounts_file),
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=30.0,
            x_monitor_refresh_cooldown_hours=3,
        ),
    )
    monkeypatch.setattr("app.services.x_monitor.TwitterApiIoClient", FakeTwitterApiIoClient)
    monkeypatch.setattr("app.services.x_monitor._utc_now", lambda: now)

    with _test_session() as session:
        service = XMonitorService(session)

        summary = service.refresh()
        health = service.health_repo.get_or_create("twitterapi.io")

        assert summary.fetched_count == 0
        assert summary.inserted_count == 0
        assert summary.next_refresh_at is None
        assert health.last_success_at is None


def test_x_monitor_refresh_with_empty_accounts_bypasses_existing_cooldown(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text('{"accounts":[]}', encoding="utf-8")
    now = datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc)
    recent_success = datetime(2026, 3, 19, 8, 30, tzinfo=timezone.utc)

    class FakeTwitterApiIoClient:
        configured = True

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            raise AssertionError("no provider request expected when account list is empty")

    monkeypatch.setattr(
        "app.services.x_monitor.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            x_monitor_accounts_file=str(accounts_file),
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=30.0,
            x_monitor_refresh_cooldown_hours=3,
        ),
    )
    monkeypatch.setattr("app.services.x_monitor.TwitterApiIoClient", FakeTwitterApiIoClient)
    monkeypatch.setattr("app.services.x_monitor._utc_now", lambda: now)

    with _test_session() as session:
        service = XMonitorService(session)
        health = service.health_repo.get_or_create("twitterapi.io")
        health.last_success_at = recent_success
        session.commit()

        summary = service.refresh()

        assert summary.skipped is False
        assert summary.next_refresh_at is None
        assert _normalize_datetime(health.last_success_at) == recent_success


def test_x_monitor_provider_health_reports_unhealthy_when_probe_fails(monkeypatch, tmp_path: Path) -> None:
    class FakeTwitterApiIoClient:
        configured = True

        def probe_account(self, handle: str) -> None:
            assert handle == "MiniMax_AI"
            raise import_module("app.services.twitterapi_io_client").TwitterApiIoError("twitterapi.io request failed with status 429")

    tmp_accounts = tmp_path / "test-health-accounts.json"
    tmp_accounts.write_text(
        '{"accounts":[{"handle":"MiniMax_AI","display_name":"MiniMax AI","market_focus":"us","is_active":true,"priority":100}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.services.x_monitor.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=30.0,
            twitterapi_io_min_interval_seconds=6.0,
            x_monitor_refresh_cooldown_hours=3,
            x_monitor_accounts_file=str(tmp_accounts),
        ),
    )
    monkeypatch.setattr("app.services.x_monitor.TwitterApiIoClient", FakeTwitterApiIoClient)

    with _test_session() as session:
        service = XMonitorService(session)

        healthy, status = service.provider_health()

        assert healthy is False
        assert status == "twitterapi.io request failed with status 429"


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


def test_x_search_endpoint_requires_query(monkeypatch) -> None:
    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def ensure_enabled(self) -> None:
            return None

    monkeypatch.setattr("app.api.routes.x_monitor.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.get("/api/x/search")

    assert response.status_code == 422


def test_x_search_endpoint_returns_normalized_rows(monkeypatch) -> None:
    now = datetime(2026, 3, 16, 7, 0, tzinfo=timezone.utc)

    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def ensure_enabled(self) -> None:
            return None

        def search_posts(self, query: str, limit: int):
            assert query == "NVDA"
            assert limit == 20
            return [
                SimpleNamespace(
                    id=0,
                    account_handle="DeItaone",
                    account_display_name="Delta One",
                    content_text="NVDA suppliers remain in focus",
                    canonical_url="https://x.com/DeItaone/status/190001",
                    market="us",
                    sentiment_label="unknown",
                    relevance_score=None,
                    posted_at=now,
                    captured_at=now,
                    symbols=["NVDA"],
                )
            ]

    monkeypatch.setattr("app.api.routes.x_monitor.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.get("/api/x/search", params={"q": "NVDA", "limit": 20})

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["account_handle"] == "DeItaone"
    assert payload[0]["symbols"] == ["NVDA"]


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
                skipped=False,
                skip_reason=None,
                next_refresh_at=None,
            )

    monkeypatch.setattr("app.api.routes.x_monitor.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.post("/api/x/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fetched_count"] == 3
    assert payload["inserted_count"] == 2
    assert payload["latency_ms"] == 1234.0
    assert payload["skipped"] is False


def test_health_endpoint_reports_x_monitor_flags(monkeypatch) -> None:
    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def provider_health(self):
            return False, "twitterapi.io request failed with status 429"

    monkeypatch.setattr(
        "app.api.routes.health.get_settings",
        lambda: SimpleNamespace(
            app_name="News Caught Backend",
            environment="test",
            stream_mode="sse",
            ai_enabled=False,
            x_monitor_enabled=True,
            twitterapi_io_api_key="test-key",
        ),
    )
    monkeypatch.setattr("app.api.routes.health.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["x_monitor_enabled"] is True
    assert payload["x_monitor_healthy"] is False


def test_x_health_endpoint_reports_provider_state(monkeypatch) -> None:
    class FakeHealthRepo:
        def get_or_create(self, provider_name: str):
            assert provider_name == "twitterapi.io"
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

        def provider_health(self):
            return True, "ok:twitterapi.io"

    monkeypatch.setattr(
        "app.api.routes.health.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            twitterapi_io_api_key="test-key",
            twitterapi_io_min_interval_seconds=6.0,
            x_monitor_refresh_cooldown_hours=3,
        ),
    )
    monkeypatch.setattr("app.api.routes.health.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.get("/api/health/x")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["configured"] is True
    assert payload["healthy"] is True
    assert payload["status"] == "ok:twitterapi.io"
    assert payload["provider_name"] == "twitterapi.io"
    assert payload["min_interval_seconds"] == 6.0
    assert payload["refresh_cooldown_hours"] == 3
