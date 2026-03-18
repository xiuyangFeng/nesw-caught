from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.article_content import ArticleContent
from app.models.llm_provider_config import LLMProviderConfig
from app.models.news_item import NewsItem
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.news_repository import NewsRepository
from app.services.llm_providers import LLMProviderError
from app.services.news_signal_pipeline import NewsSignalPipelineService


def _make_news(*, title: str, summary: str, url_hash: str) -> NewsItem:
    return NewsItem(
        source_name="Pipeline Test",
        source_url="https://example.com/pipeline",
        title=title,
        summary=summary,
        canonical_url=f"https://example.com/{url_hash}",
        url_hash=url_hash,
        market="us",
        language="en",
        sentiment_label=None,
        sentiment_score=None,
        published_at=datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc),
        fetched_at=datetime(2026, 3, 19, 9, 5, tzinfo=timezone.utc),
        ingest_status="ingested",
    )


def _cleanup_news(url_hashes: list[str]) -> None:
    with SessionLocal() as session:
        news_ids = list(session.scalars(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
        topic_ids = list(session.scalars(select(TopicNewsLink.topic_cluster_id).where(TopicNewsLink.news_id.in_(news_ids))))
        if news_ids:
            session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(news_ids)))
            session.execute(delete(TopicNewsLink).where(TopicNewsLink.news_id.in_(news_ids)))
            session.execute(delete(NewsItem).where(NewsItem.id.in_(news_ids)))
        if topic_ids:
            session.execute(delete(TopicCluster).where(TopicCluster.id.in_(topic_ids)))
        session.execute(delete(LLMProviderConfig).where(LLMProviderConfig.provider_name == "pipeline-test"))
        session.commit()


def test_process_news_ids_classifies_positive_negative_and_neutral_items() -> None:
    url_hashes = [
        "pipeline-positive",
        "pipeline-negative",
        "pipeline-neutral",
    ]
    _cleanup_news(url_hashes)

    with SessionLocal() as session:
        items = [
            _make_news(
                title="Tencent expands AI cloud revenue",
                summary="Enterprise demand improves and boosts monetization outlook.",
                url_hash=url_hashes[0],
            ),
            _make_news(
                title="Apple smartphone demand weakens",
                summary="Supplier warning points to soft shipments and lower orders.",
                url_hash=url_hashes[1],
            ),
            _make_news(
                title="Federal Reserve keeps policy unchanged",
                summary="Officials repeated existing guidance without a new market signal.",
                url_hash=url_hashes[2],
            ),
        ]
        session.add_all(items)
        session.commit()
        news_ids = [item.id for item in items]

    try:
        with SessionLocal() as session:
            NewsSignalPipelineService(session).process_news_ids(news_ids)
            session.commit()

        with SessionLocal() as session:
            stored = {
                item.url_hash: item
                for item in session.scalars(select(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
            }
            assert stored[url_hashes[0]].sentiment_label == "positive"
            assert stored[url_hashes[1]].sentiment_label == "negative"
            assert stored[url_hashes[2]].sentiment_label == "neutral"
    finally:
        _cleanup_news(url_hashes)


def test_process_news_ids_clusters_similar_news_into_one_topic_and_creates_new_topic() -> None:
    url_hashes = [
        "pipeline-apple-demand-1",
        "pipeline-apple-demand-2",
        "pipeline-oil-1",
    ]
    _cleanup_news(url_hashes)

    with SessionLocal() as session:
        items = [
            _make_news(
                title="Apple smartphone demand weakens",
                summary="Soft handset demand pressures suppliers ahead of the next cycle.",
                url_hash=url_hashes[0],
            ),
            _make_news(
                title="Apple sees softer smartphone demand",
                summary="Component commentary still points to weaker iPhone demand.",
                url_hash=url_hashes[1],
            ),
            _make_news(
                title="Oil supply risk pushes crude higher",
                summary="Shipping disruption raises energy market concern.",
                url_hash=url_hashes[2],
            ),
        ]
        session.add_all(items)
        session.commit()
        news_ids = [item.id for item in items]

    try:
        with SessionLocal() as session:
            NewsSignalPipelineService(session).process_news_ids(news_ids)
            session.commit()

        with SessionLocal() as session:
            repository = NewsRepository(session)
            topics = {
                item.url_hash: repository.get_topic_for_news(item.id)
                for item in session.scalars(select(NewsItem).where(NewsItem.url_hash.in_(url_hashes)))
            }
            assert topics[url_hashes[0]] is not None
            assert topics[url_hashes[1]] is not None
            assert topics[url_hashes[2]] is not None
            assert topics[url_hashes[0]].id == topics[url_hashes[1]].id
            assert topics[url_hashes[0]].id != topics[url_hashes[2]].id
    finally:
        _cleanup_news(url_hashes)


def test_process_news_ids_falls_back_to_rule_output_when_llm_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    url_hashes = ["pipeline-llm-fallback"]
    _cleanup_news(url_hashes)

    with SessionLocal() as session:
        session.add(
            LLMProviderConfig(
                provider_name="pipeline-test",
                display_name="Pipeline Test",
                base_url="https://example.com",
                model_name="fake-model",
                api_key="fake-key",
                is_active=True,
            )
        )
        item = _make_news(
            title="AI platform strategy remains in focus",
            summary="The outlook was described as constructive but mixed for near-term revenue timing.",
            url_hash=url_hashes[0],
        )
        session.add(item)
        session.commit()
        news_id = item.id

    def _raise_provider_error(_config):
        class _FakeProvider:
            def analyze_json(self, *, prompt: str):
                del prompt
                raise LLMProviderError("simulated llm failure")

        return _FakeProvider()

    monkeypatch.setattr(
        "app.services.news_signal_classifier.get_settings",
        lambda: type("Settings", (), {"ai_enabled": True})(),
    )
    monkeypatch.setattr("app.services.news_signal_classifier.build_provider", _raise_provider_error)

    try:
        with SessionLocal() as session:
            NewsSignalPipelineService(session).process_news_ids([news_id])
            session.commit()

        with SessionLocal() as session:
            stored = session.scalar(select(NewsItem).where(NewsItem.url_hash == url_hashes[0]))
            topic = NewsRepository(session).get_topic_for_news(stored.id)
            assert stored is not None
            assert stored.sentiment_label in {"positive", "negative", "neutral"}
            assert stored.signal_status == "processed"
            assert "simulated llm failure" in (stored.signal_error or "")
            assert topic is not None
    finally:
        _cleanup_news(url_hashes)
