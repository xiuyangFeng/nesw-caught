from datetime import datetime, timezone

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
                last_published_at=datetime(2026, 3, 23, 1, 20, tzinfo=timezone.utc),
                last_event_name="news.created_batch",
                last_error="redis unavailable",
            )

    monkeypatch.setattr("app.api.routes.stream.get_event_bus", lambda: FakeBus())

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
