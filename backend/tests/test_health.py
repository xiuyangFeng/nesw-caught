from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.source_health import SourceHealth
from app.models.worker_runtime_status import WorkerRuntimeStatus


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["stream_mode"] == "sse"
    # 数据库真实探活：默认测试库可连通，应返回 ok/True。
    assert payload["database"] == "ok"
    assert payload["database_healthy"] is True
    # 新增的运维自治字段应齐全，即使无数据也应有默认值而非缺失。
    assert "last_rss_fetch_at" in payload
    assert "last_market_quote_refresh_at" in payload
    assert set(payload["source_health_summary"]) == {"total", "disabled", "consecutive_failing"}
    assert isinstance(payload["active_stream_connections"], int)
    assert set(payload["ai_status"]) == {"enabled", "last_call_at"}
    assert payload["ai_status"]["enabled"] == payload["ai_enabled"]


def test_health_endpoint_reports_rss_and_market_quote_timestamps() -> None:
    source_name = "Health RSS Timestamp Feed"
    rss_success_at = datetime(2026, 1, 1, tzinfo=UTC)
    market_success_at = datetime(2026, 1, 2, tzinfo=UTC)

    with SessionLocal() as session:
        session.add(
            SourceHealth(
                source_name=source_name,
                market="hk",
                source_type="rss",
                last_success_at=rss_success_at,
                consecutive_failures=0,
                total_fetches=1,
                total_failures=0,
                is_disabled=False,
            )
        )
        existing_worker = session.query(WorkerRuntimeStatus).filter(
            WorkerRuntimeStatus.worker_name == "market_quote_producer"
        ).one_or_none()
        if existing_worker is None:
            session.add(
                WorkerRuntimeStatus(
                    worker_name="market_quote_producer",
                    status="ok",
                    last_success_at=market_success_at,
                    cycle_count=1,
                    success_count=1,
                    failure_count=0,
                    last_quotes_count=0,
                )
            )
        else:
            existing_worker.last_success_at = market_success_at
        session.commit()

    try:
        client = TestClient(app)
        response = client.get("/api/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["last_rss_fetch_at"] is not None
        assert payload["last_market_quote_refresh_at"] is not None
        assert payload["source_health_summary"]["total"] >= 1
    finally:
        with SessionLocal() as session:
            session.query(SourceHealth).filter(SourceHealth.source_name == source_name).delete()
            session.commit()


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
