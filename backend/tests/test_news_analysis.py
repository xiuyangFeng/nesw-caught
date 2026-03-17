from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect, text

from app.db.session import SessionLocal, engine
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.main import app


def _cleanup_llm_tables() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "news_analysis_result" in tables:
            connection.execute(text("DELETE FROM news_analysis_result"))
        if "llm_provider_config" in tables:
            connection.execute(text("DELETE FROM llm_provider_config"))


def test_get_news_analysis_returns_null_when_missing() -> None:
    _cleanup_llm_tables()
    client = TestClient(app)

    response = client.get("/api/news/1/analysis")

    assert response.status_code == 200
    assert response.json() is None


def test_post_news_analysis_requires_active_provider_config() -> None:
    _cleanup_llm_tables()
    client = TestClient(app)

    response = client.post("/api/news/1/analyze")

    assert response.status_code == 400
    assert response.json()["detail"] == "llm provider is not configured"


def test_post_news_analysis_returns_structured_result_and_persists_latest_analysis(
    monkeypatch,
) -> None:
    _cleanup_llm_tables()
    client = TestClient(app)
    client.post(
        "/api/llm/config",
        json={
            "provider_name": "openai_compatible",
            "display_name": "OpenAI Compatible",
            "base_url": "https://example-llm.test/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-test-secret",
        },
    )

    def fake_analyze_json(self, *, prompt: str):  # type: ignore[no-untyped-def]
        assert "Tencent expands enterprise AI product suite" in prompt
        return {
            "top_pick": {
                "symbol": "0700.HK",
                "market": "hk",
                "company_name": "Tencent",
                "confidence": 0.92,
                "reason": "Enterprise AI product momentum directly benefits Tencent.",
            },
            "candidates": [
                {
                    "symbol": "0700.HK",
                    "market": "hk",
                    "company_name": "Tencent",
                    "confidence": 0.92,
                    "reason": "Enterprise AI product momentum directly benefits Tencent.",
                }
            ],
            "summary": "Tencent enterprise AI momentum remains the clearest equity read-through.",
            "risk_notes": "Body coverage is limited to a single source.",
            "sentiment": "positive",
            "context_limitations": None,
        }

    monkeypatch.setattr(
        "app.services.llm_providers.OpenAICompatibleProvider.analyze_json",
        fake_analyze_json,
    )

    response = client.post("/api/news/1/analyze")

    assert response.status_code == 200
    payload = response.json()
    assert payload["top_pick"]["symbol"] == "0700.HK"
    assert payload["provider_name"] == "openai_compatible"
    assert payload["model_name"] == "deepseek-chat"
    assert payload["candidates"][0]["symbol"] == "0700.HK"
    assert payload["summary"].startswith("Tencent")

    follow_up = client.get("/api/news/1/analysis")
    assert follow_up.status_code == 200
    cached = follow_up.json()
    assert cached["top_pick"]["symbol"] == "0700.HK"
    assert cached["provider_name"] == "openai_compatible"


def test_post_news_analysis_marks_context_limitations_when_article_body_missing(monkeypatch) -> None:
    _cleanup_llm_tables()
    client = TestClient(app)
    client.post(
        "/api/llm/config",
        json={
            "provider_name": "openai_compatible",
            "display_name": "OpenAI Compatible",
            "base_url": "https://example-llm.test/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-test-secret",
        },
    )

    url_hash = "seed-analysis-no-body"
    with SessionLocal() as session:
        session.execute(delete(ArticleContent).where(ArticleContent.news_id == 999999))
        session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
        news_item = NewsItem(
            source_name="Analysis Test",
            source_url="https://example.com/analysis/no-body",
            title="Cloud software vendor signs major AI infrastructure deal",
            summary="The company announced a large AI deal without naming listed partners directly.",
            canonical_url="https://example.com/analysis/no-body-story",
            url_hash=url_hash,
            market="us",
            language="en",
            sentiment_label=None,
            sentiment_score=None,
            published_at=datetime.now(timezone.utc),
            fetched_at=datetime.now(timezone.utc),
            ingest_status="ingested",
        )
        session.add(news_item)
        session.commit()
        news_id = news_item.id

    def fake_analyze_json(self, *, prompt: str):  # type: ignore[no-untyped-def]
        assert "Cloud software vendor signs major AI infrastructure deal" in prompt
        return {
            "top_pick": None,
            "candidates": [],
            "summary": "Context is limited because only title and summary were available.",
            "risk_notes": "Insufficient body text for a high-confidence mapping.",
            "sentiment": "neutral",
            "context_limitations": "article body missing",
        }

    monkeypatch.setattr(
        "app.services.llm_providers.OpenAICompatibleProvider.analyze_json",
        fake_analyze_json,
    )

    try:
        response = client.post(f"/api/news/{news_id}/analyze")

        assert response.status_code == 200
        payload = response.json()
        assert payload["top_pick"] is None
        assert payload["context_limitations"] == "article body missing"
    finally:
        with SessionLocal() as session:
            session.execute(delete(NewsItem).where(NewsItem.url_hash == url_hash))
            session.commit()


def test_post_news_analysis_rejects_invalid_provider_payload(monkeypatch) -> None:
    _cleanup_llm_tables()
    client = TestClient(app)
    client.post(
        "/api/llm/config",
        json={
            "provider_name": "openai_compatible",
            "display_name": "OpenAI Compatible",
            "base_url": "https://example-llm.test/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-test-secret",
        },
    )

    def fake_analyze_json(self, *, prompt: str):  # type: ignore[no-untyped-def]
        return "not-json"

    monkeypatch.setattr(
        "app.services.llm_providers.OpenAICompatibleProvider.analyze_json",
        fake_analyze_json,
    )

    response = client.post("/api/news/1/analyze")

    assert response.status_code == 502
    assert response.json()["detail"] == "llm provider returned invalid analysis payload"
