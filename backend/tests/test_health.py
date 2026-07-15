from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.source_health import SourceHealth


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["stream_mode"] == "sse"


def test_health_sources_endpoint_includes_market() -> None:
    source_name = "Health Projection Feed"
    with SessionLocal() as session:
        session.add(
            SourceHealth(
                source_name=source_name,
                market="hk",
                source_type="rss",
                consecutive_failures=0,
                total_fetches=1,
                total_failures=0,
                is_disabled=False,
            )
        )
        session.commit()

    try:
        client = TestClient(app)
        response = client.get("/api/health/sources")

        assert response.status_code == 200
        payload = response.json()
        row = next(item for item in payload if item["source_name"] == source_name)
        assert row["market"] == "hk"
    finally:
        with SessionLocal() as session:
            session.query(SourceHealth).filter(SourceHealth.source_name == source_name).delete()
            session.commit()
