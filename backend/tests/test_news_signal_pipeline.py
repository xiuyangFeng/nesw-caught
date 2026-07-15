from datetime import UTC, datetime

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


@pytest.fixture(autouse=True)
def _block_real_article_crawling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep these tests offline: without this, _ensure_articles() really fetches
    the https://example.com/... seed URLs through the shared crawl client and
    leaks pooled TLS connections at process exit. Crawl failure is the graceful
    path the pipeline already supports; classification falls back to
    title/summary, which is all these tests assert on."""

    def _no_network(url: str, timeout: float = 15.0) -> str:
        raise RuntimeError(f"network disabled in tests (tried to crawl {url})")

    monkeypatch.setattr(
        "app.services.news_signal_pipeline.crawl_and_extract_article", _no_network
    )


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
        published_at=datetime(2026, 3, 19, 9, 0, tzinfo=UTC),
        fetched_at=datetime(2026, 3, 19, 9, 5, tzinfo=UTC),
        ingest_status="ingested",
    )


def _cleanup_news(url_hashes: list[str]) -> None:
    with SessionLocal() as session:
        news_ids = list(
            session.scalars(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes)))
        )
        topic_ids = list(
            session.scalars(
                select(TopicNewsLink.topic_cluster_id).where(TopicNewsLink.news_id.in_(news_ids))
            )
        )
        if news_ids:
            session.execute(delete(ArticleContent).where(ArticleContent.news_id.in_(news_ids)))
            session.execute(delete(TopicNewsLink).where(TopicNewsLink.news_id.in_(news_ids)))
            session.execute(delete(NewsItem).where(NewsItem.id.in_(news_ids)))
        if topic_ids:
            session.execute(delete(TopicCluster).where(TopicCluster.id.in_(topic_ids)))
        session.execute(
            delete(LLMProviderConfig).where(LLMProviderConfig.provider_name == "pipeline-test")
        )
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
                for item in session.scalars(
                    select(NewsItem).where(NewsItem.url_hash.in_(url_hashes))
                )
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
                for item in session.scalars(
                    select(NewsItem).where(NewsItem.url_hash.in_(url_hashes))
                )
            }
            assert topics[url_hashes[0]] is not None
            assert topics[url_hashes[1]] is not None
            assert topics[url_hashes[2]] is not None
            assert topics[url_hashes[0]].id == topics[url_hashes[1]].id
            assert topics[url_hashes[0]].id != topics[url_hashes[2]].id
    finally:
        _cleanup_news(url_hashes)


def test_process_news_ids_falls_back_to_rule_output_when_llm_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_news_created_batch_handler_publishes_news_updated_after_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as main_module
    from app.workers.queue_worker import analysis_queue

    while not analysis_queue.empty():
        try:
            analysis_queue.get_nowait()
        except Exception:
            break

    news_id = 4242

    class FakeBus:
        def __init__(self) -> None:
            self.handlers: dict[str, list] = {}
            self.published: list[tuple[str, dict[str, object]]] = []

        def subscribe(self, event_name: str, handler) -> None:
            self.handlers.setdefault(event_name, []).append(handler)

        def publish(self, event_name: str, payload: dict[str, object]) -> None:
            self.published.append((event_name, payload))
            for handler in self.handlers.get(event_name, []):
                handler(payload)

    class FakePipelineService:
        def __init__(self, session, session_factory=None) -> None:
            self.session = session
            self.session_factory = session_factory

        def process_news_ids(self, news_ids: list[int]):
            assert news_ids == [news_id]
            return type(
                "Summary", (), {"news_ids": list(news_ids), "processed_count": len(news_ids)}
            )()

    class FakeNewsRepository:
        def __init__(self, session) -> None:
            self.session = session

        def get_by_id(self, requested_id: int) -> NewsItem:
            assert requested_id == news_id
            item = _make_news(
                title="Processed headline",
                summary="Processed summary",
                url_hash="pipeline-news-updated",
            )
            item.id = news_id
            item.source_name = "Reuters"
            item.canonical_url = "https://example.com/story"
            item.sentiment_label = "positive"
            item.fetched_at = datetime(2026, 3, 25, 2, 31, 3, tzinfo=UTC)
            item.published_at = datetime(2026, 3, 25, 2, 30, tzinfo=UTC)
            return item

        def get_by_ids(self, requested_ids: list[int]) -> list[NewsItem]:
            return [self.get_by_id(rid) for rid in requested_ids]

    class FakeNotificationService:
        def on_news_created(self, payload: dict[str, object]) -> None:
            del payload

        def on_analysis_completed(self, payload: dict[str, object]) -> None:
            del payload

    fake_bus = FakeBus()
    monkeypatch.setattr(main_module, "build_event_bus", lambda: fake_bus)
    monkeypatch.setattr(main_module, "NewsSignalPipelineService", FakePipelineService)
    monkeypatch.setattr(main_module, "NewsRepository", FakeNewsRepository)
    monkeypatch.setattr(main_module, "get_notification_service", lambda: FakeNotificationService())

    main_module._register_event_handlers()
    fake_bus.publish("news.created_batch", {"news_ids": [news_id]})

    # Simulate background queue worker consumption
    from app.workers.queue_worker import BackgroundQueueWorker
    # Create a dummy session that matches context manager protocol
    class DummySession:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def commit(self): pass
        def close(self): pass
        def execute(self, *args, **kwargs):
            class DummyResult:
                def scalars(self):
                    return type("Scalar", (), {"all": lambda: [], "first": lambda: None})()
            return DummyResult()

    # Also monkeypatch the worker's imports to use the fakes
    monkeypatch.setattr("app.workers.queue_worker.NewsSignalPipelineService", FakePipelineService)
    monkeypatch.setattr("app.workers.queue_worker.NewsRepository", FakeNewsRepository)

    qw = BackgroundQueueWorker(session_factory=lambda: DummySession())
    qw.run_cycle()

    assert (
        "news.updated",
        {
            "id": news_id,
            "title": "Processed headline",
            "summary": "Processed summary",
            "source_name": "Reuters",
            "canonical_url": "https://example.com/story",
            "market": "us",
            "sentiment_label": "positive",
            "editorial_score": None,
            "published_at": "2026-03-25T02:30:00Z",
            "fetched_at": "2026-03-25T02:31:03Z",
            "updated_fields": ["sentiment_label"],
        },
    ) in fake_bus.published


def test_chinese_positive_sentiment_classified_correctly() -> None:
    url_hashes = ["pipeline-zh-positive", "pipeline-zh-negative", "pipeline-zh-neutral"]
    _cleanup_news(url_hashes)

    with SessionLocal() as session:
        items = [
            _make_news(
                title="营收大涨超预期 芯片业务强劲增长",
                summary="公司业绩突破新高，看好后续发展机遇。",
                url_hash=url_hashes[0],
            ),
            _make_news(
                title="股价暴跌 市场承压 疲软信号明显",
                summary="利空消息导致崩盘风险加剧，制裁压力加大。",
                url_hash=url_hashes[1],
            ),
            _make_news(
                title="公司发布新品展示技术路线",
                summary="展会上展示了多种产品和应用场景。",
                url_hash=url_hashes[2],
            ),
        ]
        for item in items:
            item.language = "zh"
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
                for item in session.scalars(
                    select(NewsItem).where(NewsItem.url_hash.in_(url_hashes))
                )
            }
            assert stored[url_hashes[0]].sentiment_label == "positive"
            assert stored[url_hashes[1]].sentiment_label == "negative"
            assert stored[url_hashes[2]].sentiment_label == "neutral"
    finally:
        _cleanup_news(url_hashes)


def test_chinese_theme_words_contribute_to_topic_key() -> None:
    url_hash = "pipeline-zh-theme"
    _cleanup_news([url_hash])

    with SessionLocal() as session:
        item = _make_news(
            title="台积电芯片产能扩产 供应链订单大幅增长",
            summary="半导体出货提速，AI模型需求强劲。",
            url_hash=url_hash,
        )
        item.language = "zh"
        session.add(item)
        session.commit()
        news_id = item.id

    try:
        with SessionLocal() as session:
            NewsSignalPipelineService(session).process_news_ids([news_id])
            session.commit()

        with SessionLocal() as session:
            topic = NewsRepository(session).get_topic_for_news(news_id)
            assert topic is not None
            topic_keywords = [
                k.strip().lower() for k in (topic.keywords or "").split(",") if k.strip()
            ]
            zh_themes = {"芯片", "产能", "供应链", "半导体", "出货", "模型"}
            assert any(kw in zh_themes for kw in topic_keywords)
    finally:
        _cleanup_news([url_hash])
