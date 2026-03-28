from __future__ import annotations

import json
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
from app.models.x_account import XAccount
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
        import_result = service.import_accounts_from_file()
        first = service.refresh()
        second = service.refresh()

        assert import_result.created_count == 1
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
        service.import_accounts_from_file()
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
        service.import_accounts_from_file()

        healthy, status = service.provider_health()

        assert healthy is False
        assert status == "twitterapi.io request failed with status 429"


def test_x_accounts_endpoint_returns_tier_and_source(monkeypatch) -> None:
    class FakeAccounts:
        def list_all(self):
            return [
                SimpleNamespace(
                    id=1,
                    handle="DeItaone",
                    display_name="Delta One",
                    market_focus="us",
                    is_active=True,
                    priority=100,
                    tier="core",
                    source="manual",
                    notes="Macro and breaking market headlines",
                )
            ]

    class FakeService:
        def __init__(self, session) -> None:
            self.session = session
            self.accounts = FakeAccounts()

        def ensure_enabled(self) -> None:
            return None

        def sync_accounts_from_file(self):
            return []

    monkeypatch.setattr("app.api.routes.x_monitor.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.get("/api/x/accounts")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["tier"] == "core"
    assert payload[0]["source"] == "manual"


def test_x_accounts_create_endpoint_normalizes_handle_and_defaults_tier(monkeypatch) -> None:
    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def ensure_enabled(self) -> None:
            return None

        def create_account(self, payload):
            assert payload.handle == "DeItaone"
            assert payload.display_name == "Delta One"
            assert payload.tier == "watch"
            return SimpleNamespace(
                id=1,
                handle="DeItaone",
                display_name="Delta One",
                market_focus="us",
                is_active=True,
                priority=100,
                tier="watch",
                source="manual",
                notes=None,
            )

    monkeypatch.setattr("app.api.routes.x_monitor.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.post(
        "/api/x/accounts",
        json={
            "handle": "@DeItaone",
            "display_name": "Delta One",
            "market_focus": "us",
            "priority": 100,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["handle"] == "DeItaone"
    assert payload["tier"] == "watch"
    assert payload["source"] == "manual"


def test_x_accounts_patch_endpoint_updates_existing_account(monkeypatch) -> None:
    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def ensure_enabled(self) -> None:
            return None

        def update_account(self, handle: str, payload):
            assert handle == "DeItaone"
            assert payload.display_name == "Delta One Fast"
            assert payload.tier == "core"
            assert payload.priority == 120
            assert payload.is_active is False
            assert payload.notes == "Higher signal only"
            return SimpleNamespace(
                id=1,
                handle=handle,
                display_name=payload.display_name,
                market_focus="us",
                is_active=payload.is_active,
                priority=payload.priority,
                tier=payload.tier,
                source="manual",
                notes=payload.notes,
            )

    monkeypatch.setattr("app.api.routes.x_monitor.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.patch(
        "/api/x/accounts/DeItaone",
        json={
            "display_name": "Delta One Fast",
            "tier": "core",
            "priority": 120,
            "is_active": False,
            "notes": "Higher signal only",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tier"] == "core"
    assert payload["is_active"] is False


def test_x_accounts_delete_endpoint_removes_account(monkeypatch) -> None:
    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def ensure_enabled(self) -> None:
            return None

        def delete_account(self, handle: str) -> None:
            assert handle == "DeItaone"

    monkeypatch.setattr("app.api.routes.x_monitor.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.delete("/api/x/accounts/DeItaone")

    assert response.status_code == 204


def test_x_monitor_refresh_uses_database_accounts_without_implicit_file_sync(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(
        '{"accounts":[{"handle":"DeItaone","display_name":"Delta One","market_focus":"us","is_active":true,"priority":100,"tier":"core"}]}',
        encoding="utf-8",
    )

    class FakeTwitterApiIoClient:
        configured = True

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            raise AssertionError("refresh should not pull accounts directly from file")

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
        summary = service.refresh()

        assert summary.fetched_count == 0
        assert summary.inserted_count == 0
        assert service.accounts.list_all() == []


def test_x_monitor_import_accounts_from_file_returns_counts_and_marks_source(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "handle": "DeItaone",
                        "display_name": "Delta One",
                        "market_focus": "us",
                        "is_active": True,
                        "priority": 100,
                        "tier": "core",
                    },
                    {
                        "handle": "SawyerMerritt",
                        "display_name": "Sawyer Merritt",
                        "market_focus": "us",
                        "is_active": True,
                        "priority": 80,
                        "tier": "watch",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

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

    with _test_session() as session:
        session.add(
            XAccount(
                handle="SawyerMerritt",
                display_name="Sawyer Old",
                market_focus="us",
                is_active=True,
                priority=10,
                tier="watch",
                source="manual",
                notes=None,
            )
        )
        session.add(
            XAccount(
                handle="ExistingOnly",
                display_name="Existing Only",
                market_focus="us",
                is_active=True,
                priority=1,
                tier="watch",
                source="manual",
                notes=None,
            )
        )
        session.commit()

        service = XMonitorService(session)
        result = service.import_accounts_from_file()
        rows = service.accounts.list_all()

        assert result.created_count == 1
        assert result.updated_count == 1
        assert result.skipped_count == 0
        assert {row.handle for row in rows} == {"DeItaone", "SawyerMerritt", "ExistingOnly"}
        imported = {row.handle: row for row in rows}
        assert imported["DeItaone"].source == "file_import"
        assert imported["SawyerMerritt"].source == "file_import"


def test_x_monitor_export_accounts_to_file_writes_stable_order(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"

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

    with _test_session() as session:
        session.add_all(
            [
                XAccount(
                    handle="ZuluDesk",
                    display_name="Zulu Desk",
                    market_focus="us",
                    is_active=True,
                    priority=50,
                    tier="watch",
                    source="manual",
                    notes="B",
                ),
                XAccount(
                    handle="AlphaDesk",
                    display_name="Alpha Desk",
                    market_focus="us",
                    is_active=True,
                    priority=50,
                    tier="core",
                    source="manual",
                    notes="A",
                ),
            ]
        )
        session.commit()

        service = XMonitorService(session)
        result = service.export_accounts_to_file()

        assert result.exported_count == 2
        payload = json.loads(accounts_file.read_text(encoding="utf-8"))
        assert [item["handle"] for item in payload["accounts"]] == ["AlphaDesk", "ZuluDesk"]
        assert payload["accounts"][0]["tier"] == "core"
        assert payload["accounts"][0]["source"] == "manual"


def test_x_monitor_refresh_prioritizes_core_before_watch_and_excludes_muted(monkeypatch) -> None:
    seen_handles: list[str] = []

    class FakeTwitterApiIoClient:
        configured = True

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            seen_handles.append(handle)
            return []

    monkeypatch.setattr(
        "app.services.x_monitor.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            x_monitor_accounts_file=None,
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=30.0,
            x_monitor_refresh_cooldown_hours=0,
        ),
    )
    monkeypatch.setattr("app.services.x_monitor.TwitterApiIoClient", FakeTwitterApiIoClient)

    with _test_session() as session:
        session.add_all(
            [
                XAccount(
                    handle="WatchDesk",
                    display_name="Watch Desk",
                    market_focus="us",
                    is_active=True,
                    priority=200,
                    tier="watch",
                    source="manual",
                    notes=None,
                ),
                XAccount(
                    handle="CoreDesk",
                    display_name="Core Desk",
                    market_focus="us",
                    is_active=True,
                    priority=50,
                    tier="core",
                    source="manual",
                    notes=None,
                ),
                XAccount(
                    handle="MutedDesk",
                    display_name="Muted Desk",
                    market_focus="us",
                    is_active=True,
                    priority=999,
                    tier="muted",
                    source="manual",
                    notes=None,
                ),
            ]
        )
        session.commit()

        service = XMonitorService(session)
        summary = service.refresh()

        assert summary.fetched_count == 0
        assert seen_handles == ["CoreDesk", "WatchDesk"]


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


def test_x_monitor_refresh_builds_macro_and_resonance_signals(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "handle": "DeItaone",
                        "display_name": "Delta One",
                        "market_focus": "us",
                        "is_active": True,
                        "priority": 100,
                        "tier": "core",
                    },
                    {
                        "handle": "WalterBloomberg",
                        "display_name": "Walter Bloomberg",
                        "market_focus": "us",
                        "is_active": True,
                        "priority": 90,
                        "tier": "watch",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeTwitterApiIoClient:
        configured = True

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            tweets = {
                "DeItaone": [
                    {
                        "id": "200001",
                        "text": "US tariff talk on AI chip exports is escalating for NVDA and AMD suppliers",
                        "createdAt": "2026-03-28T07:00:00Z",
                        "url": "https://x.com/DeItaone/status/200001",
                        "symbols": ["NVDA", "AMD"],
                        "author": {"userName": "DeItaone", "name": "Delta One"},
                    }
                ],
                "WalterBloomberg": [
                    {
                        "id": "200002",
                        "text": "Export control and tariff headlines keep hitting semis this morning",
                        "createdAt": "2026-03-28T07:20:00Z",
                        "url": "https://x.com/WalterBloomberg/status/200002",
                        "symbols": ["NVDA"],
                        "author": {"userName": "WalterBloomberg", "name": "Walter Bloomberg"},
                    }
                ],
            }
            return tweets[handle]

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
        service.import_accounts_from_file()

        summary = service.refresh()

        assert summary.inserted_count == 2

        signal_module = import_module("app.models.x_signal")
        XSignal = signal_module.XSignal
        signals = session.query(XSignal).order_by(XSignal.priority_score.desc(), XSignal.id.asc()).all()

        assert len(signals) >= 2
        assert any(signal.signal_type == "macro_event" and signal.macro_tag == "tariff" for signal in signals)
        assert any(signal.signal_type == "multi_account_resonance" and signal.source_count == 2 for signal in signals)


def test_x_monitor_service_returns_radar_payload(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(
        '{"accounts":[{"handle":"DeItaone","display_name":"Delta One","market_focus":"us","is_active":true,"priority":100,"tier":"core"}]}',
        encoding="utf-8",
    )

    class FakeTwitterApiIoClient:
        configured = True

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            return [
                {
                    "id": "210001",
                    "text": "Fed rate cut odds are moving after new CPI headlines",
                    "createdAt": "2026-03-28T08:00:00Z",
                    "url": "https://x.com/DeItaone/status/210001",
                    "symbols": ["SPY"],
                    "author": {"userName": "DeItaone", "name": "Delta One"},
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
        service.import_accounts_from_file()
        service.refresh()

        radar = service.get_radar(limit=10)

        assert len(radar.priority_signals) >= 1
        assert len(radar.macro_clusters) >= 1
        assert len(radar.evidence_stream) >= 1
        assert radar.priority_signals[0].signal_type in {"account_post", "macro_event", "multi_account_resonance"}


def test_x_radar_endpoint_returns_priority_signals(monkeypatch) -> None:
    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def ensure_enabled(self) -> None:
            return None

        def get_radar(self, limit: int = 50):
            schema_module = import_module("app.schemas.x_monitor")
            return schema_module.XRadarResponse(
                priority_signals=[
                    schema_module.XRadarSignalView(
                        id=1,
                        signal_type="macro_event",
                        title="Tariff pressure hits semis",
                        summary="Two tracked accounts flagged tariff risk around AI chips.",
                        market="us",
                        topic_tag="semis",
                        macro_tag="tariff",
                        primary_symbol="NVDA",
                        priority_score=95.0,
                        confidence_score=0.86,
                        source_count=2,
                        first_seen_at=datetime(2026, 3, 28, 7, 0, tzinfo=timezone.utc),
                        last_seen_at=datetime(2026, 3, 28, 7, 20, tzinfo=timezone.utc),
                    )
                ],
                macro_clusters=[
                    schema_module.XRadarMacroClusterView(
                        macro_tag="tariff",
                        title="Tariff Watch",
                        signal_count=1,
                        source_count=2,
                        top_signal_ids=[1],
                    )
                ],
                evidence_stream=[],
            )

    monkeypatch.setattr("app.api.routes.x_monitor.XMonitorService", FakeService)

    client = TestClient(app)
    response = client.get("/api/x/radar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["priority_signals"][0]["macro_tag"] == "tariff"
    assert payload["macro_clusters"][0]["source_count"] == 2


def test_x_monitor_refresh_uses_external_radar_rules_file(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    rules_file = tmp_path / "x_radar_rules.json"
    accounts_file.write_text(
        '{"accounts":[{"handle":"DeItaone","display_name":"Delta One","market_focus":"us","is_active":true,"priority":100,"tier":"core"}]}',
        encoding="utf-8",
    )
    rules_file.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "tag": "policy_shift",
                        "title": "Policy Shift",
                        "topic_tag": "macro",
                        "keywords": ["white house", "executive order"],
                        "weight": 77.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeTwitterApiIoClient:
        configured = True

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            return [
                {
                    "id": "220001",
                    "text": "White House executive order is pushing a new policy shift around AI exports",
                    "createdAt": "2026-03-28T08:00:00Z",
                    "url": "https://x.com/DeItaone/status/220001",
                    "symbols": ["NVDA"],
                    "author": {"userName": "DeItaone", "name": "Delta One"},
                }
            ]

    monkeypatch.setattr(
        "app.services.x_monitor.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            x_monitor_accounts_file=str(accounts_file),
            x_radar_rules_file=str(rules_file),
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=30.0,
            x_monitor_refresh_cooldown_hours=0,
        ),
    )
    monkeypatch.setattr("app.services.x_monitor.TwitterApiIoClient", FakeTwitterApiIoClient)

    with _test_session() as session:
        service = XMonitorService(session)
        service.import_accounts_from_file()
        service.refresh()

        signal_module = import_module("app.models.x_signal")
        XSignal = signal_module.XSignal
        signal = session.query(XSignal).filter(XSignal.macro_tag == "policy_shift").one()

        assert signal.title == "Policy Shift signal from tracked accounts"
        assert signal.priority_score >= 127.0


def test_x_monitor_refresh_falls_back_when_rules_file_contains_invalid_weight(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    rules_file = tmp_path / "x_radar_rules.json"
    accounts_file.write_text(
        '{"accounts":[{"handle":"DeItaone","display_name":"Delta One","market_focus":"us","is_active":true,"priority":100,"tier":"core"}]}',
        encoding="utf-8",
    )
    rules_file.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "tag": "bad_rule",
                        "title": "Bad Rule",
                        "topic_tag": "macro",
                        "keywords": ["tariff"],
                        "weight": "oops",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeTwitterApiIoClient:
        configured = True

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            return [
                {
                    "id": "220002",
                    "text": "Tariff pressure is building around AI chip exports",
                    "createdAt": "2026-03-28T08:00:00Z",
                    "url": "https://x.com/DeItaone/status/220002",
                    "symbols": ["NVDA"],
                    "author": {"userName": "DeItaone", "name": "Delta One"},
                }
            ]

    monkeypatch.setattr(
        "app.services.x_monitor.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            x_monitor_accounts_file=str(accounts_file),
            x_radar_rules_file=str(rules_file),
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=30.0,
            x_monitor_refresh_cooldown_hours=0,
        ),
    )
    monkeypatch.setattr("app.services.x_monitor.TwitterApiIoClient", FakeTwitterApiIoClient)

    with _test_session() as session:
        service = XMonitorService(session)
        service.import_accounts_from_file()
        summary = service.refresh()

        assert summary.inserted_count == 1

        signal_module = import_module("app.models.x_signal")
        XSignal = signal_module.XSignal
        signal = session.query(XSignal).filter(XSignal.macro_tag == "tariff").one()
        assert signal.title == "Tariff signal from tracked accounts"


def test_x_monitor_service_honors_radar_limit_for_macro_clusters(monkeypatch, tmp_path: Path) -> None:
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(
        json.dumps(
            {
                "accounts": [
                    {"handle": "DeItaone", "display_name": "Delta One", "market_focus": "us", "is_active": True, "priority": 100, "tier": "core"},
                    {"handle": "WalterBloomberg", "display_name": "Walter Bloomberg", "market_focus": "us", "is_active": True, "priority": 90, "tier": "watch"},
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeTwitterApiIoClient:
        configured = True

        def get_user_last_tweets(self, handle: str, limit: int = 20) -> list[dict[str, object]]:
            tweets = {
                "DeItaone": [
                    {
                        "id": "230001",
                        "text": "Tariff headlines are back for AI chips",
                        "createdAt": "2026-03-28T07:00:00Z",
                        "url": "https://x.com/DeItaone/status/230001",
                        "symbols": ["NVDA"],
                        "author": {"userName": "DeItaone", "name": "Delta One"},
                    },
                    {
                        "id": "230002",
                        "text": "Fed speakers are shifting rate expectations",
                        "createdAt": "2026-03-28T07:10:00Z",
                        "url": "https://x.com/DeItaone/status/230002",
                        "symbols": ["SPY"],
                        "author": {"userName": "DeItaone", "name": "Delta One"},
                    },
                ],
                "WalterBloomberg": [
                    {
                        "id": "230003",
                        "text": "Export control chatter is hitting semis again",
                        "createdAt": "2026-03-28T07:20:00Z",
                        "url": "https://x.com/WalterBloomberg/status/230003",
                        "symbols": ["NVDA"],
                        "author": {"userName": "WalterBloomberg", "name": "Walter Bloomberg"},
                    }
                ],
            }
            return tweets[handle]

    monkeypatch.setattr(
        "app.services.x_monitor.get_settings",
        lambda: SimpleNamespace(
            x_monitor_enabled=True,
            x_monitor_accounts_file=str(accounts_file),
            twitterapi_io_api_key="test-key",
            twitterapi_io_timeout_seconds=30.0,
            x_monitor_refresh_cooldown_hours=0,
            x_radar_rules_file=None,
        ),
    )
    monkeypatch.setattr("app.services.x_monitor.TwitterApiIoClient", FakeTwitterApiIoClient)

    with _test_session() as session:
        service = XMonitorService(session)
        service.import_accounts_from_file()
        service.refresh()

        radar = service.get_radar(limit=1)

        assert len(radar.priority_signals) == 1
        assert len(radar.macro_clusters) == 1
        assert len(radar.evidence_stream) == 1
