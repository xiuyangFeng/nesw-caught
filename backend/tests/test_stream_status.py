from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.services.event_bus import EventBusStatus


def test_stream_status_reports_event_bus_health(monkeypatch) -> None:
    class FakeBus:
        def get_status(self) -> EventBusStatus:
            return EventBusStatus(
                backend="hybrid",
                status="degraded",
                redis_enabled=True,
                last_published_at=datetime(2026, 3, 23, 1, 20, tzinfo=UTC),
                last_event_name="news.created_batch",
                last_error="redis unavailable",
            )

    monkeypatch.setattr("app.api.routes.stream.get_event_bus", lambda: FakeBus())
    monkeypatch.setattr("app.api.routes.stream.get_market_worker_runtime_status", lambda session: None)

    client = TestClient(app)
    response = client.get("/api/stream/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "sse"
    assert payload["status"] == "degraded"
    assert payload["backend"] == "hybrid"
    assert payload["redis_enabled"] is True
    assert payload["last_event_name"] == "news.created_batch"
    assert payload["last_error"] == "redis unavailable"
    assert payload["market_worker"] is None


def test_stream_status_reports_market_worker_runtime(monkeypatch) -> None:
    class FakeBus:
        def get_status(self) -> EventBusStatus:
            return EventBusStatus(
                backend="hybrid",
                status="ok",
                redis_enabled=True,
            )

    monkeypatch.setattr("app.api.routes.stream.get_event_bus", lambda: FakeBus())
    monkeypatch.setattr(
        "app.api.routes.stream.get_market_worker_runtime_status",
        lambda session: {
            "name": "market_quote_producer",
            "status": "ok",
            "last_heartbeat_at": datetime(2026, 3, 23, 5, 0, tzinfo=UTC),
            "last_success_at": datetime(2026, 3, 23, 4, 59, tzinfo=UTC),
            "last_failure_at": None,
            "last_error": None,
            "cycle_count": 12,
            "success_count": 11,
            "failure_count": 1,
            "last_quotes_count": 2,
        },
    )

    client = TestClient(app)
    response = client.get("/api/stream/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market_worker"]["name"] == "market_quote_producer"
    assert payload["market_worker"]["status"] == "ok"
    assert payload["market_worker"]["cycle_count"] == 12
    assert payload["market_worker"]["success_count"] == 11
    assert payload["market_worker"]["failure_count"] == 1
    assert payload["market_worker"]["last_quotes_count"] == 2
