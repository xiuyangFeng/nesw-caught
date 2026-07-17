"""POST /api/news/refresh 服务端 lease/cooldown 回归测试。"""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.services.news_ingestion import RefreshSummary, SourceFetchResult
from app.services.news_refresh_lease import reset_news_refresh_lease


def _fake_ingestion(monkeypatch) -> None:
    class FakeIngestionService:
        def __init__(self, session) -> None:
            self.session = session

        def refresh_all(self) -> RefreshSummary:
            now = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)
            return RefreshSummary(
                started_at=now,
                finished_at=now,
                fetched_count=1,
                inserted_count=0,
                results=[
                    SourceFetchResult(
                        source_name="The Verge",
                        source_type="rss",
                        status="ok",
                        fetched_count=1,
                        inserted_count=0,
                        error=None,
                        latency_ms=10.0,
                    )
                ],
            )

    monkeypatch.setattr("app.api.routes.news.NewsIngestionService", FakeIngestionService)


def test_refresh_news_endpoint_rejects_during_cooldown(monkeypatch) -> None:
    reset_news_refresh_lease()
    _fake_ingestion(monkeypatch)
    get_settings.cache_clear()
    monkeypatch.setenv("NEWS_REFRESH_COOLDOWN_SECONDS", "60")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.news_refresh_lease.get_settings",
        lambda: Settings(news_refresh_cooldown_seconds=60, verify_app_token=False),
    )
    monkeypatch.setattr(
        "app.api.routes.news.get_settings",
        lambda: Settings(news_refresh_cooldown_seconds=60, verify_app_token=False),
    )

    client = TestClient(app)
    first = client.post("/api/news/refresh")
    assert first.status_code == 200

    second = client.post("/api/news/refresh")
    assert second.status_code == 429
    payload = second.json()
    assert "cooldown" in str(payload.get("detail", "")).lower() or "冷却" in str(payload.get("detail", ""))
    assert "Retry-After" in second.headers
    assert float(second.headers["Retry-After"]) > 0

    reset_news_refresh_lease()
    get_settings.cache_clear()


def test_refresh_news_endpoint_allows_after_lease_reset(monkeypatch) -> None:
    reset_news_refresh_lease()
    _fake_ingestion(monkeypatch)
    monkeypatch.setattr(
        "app.services.news_refresh_lease.get_settings",
        lambda: Settings(news_refresh_cooldown_seconds=60, verify_app_token=False),
    )

    client = TestClient(app)
    assert client.post("/api/news/refresh").status_code == 200
    reset_news_refresh_lease()
    assert client.post("/api/news/refresh").status_code == 200
    reset_news_refresh_lease()
