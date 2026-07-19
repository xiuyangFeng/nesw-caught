"""Observability test for optimization-plan.md #12: `_safe_crawl` in
`app/services/news_signal_pipeline.py` catches broad `except Exception` around
a single article's crawl attempt so one failure doesn't break the whole batch
(existing semantics: the article is marked `extract_status="failed"` and the
pipeline still classifies from title/summary). This file verifies the
swallowed failure is now counted instead of only appearing in a log line.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.services.news_signal_pipeline import NewsSignalPipelineService, get_pipeline_error_counts


@pytest.fixture(autouse=True)
def _block_real_article_crawling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep this test offline (mirrors the fixture in test_news_signal_pipeline.py):
    without it, `_ensure_articles()` would really try to fetch the seed URL."""

    def _no_network(url: str, timeout: float = 15.0) -> str:
        raise RuntimeError(f"network disabled in tests (tried to crawl {url})")

    monkeypatch.setattr("app.services.news_signal_pipeline.crawl_and_extract_article", _no_network)


def _make_news(*, title: str, summary: str, url_hash: str) -> NewsItem:
    published_at = datetime(2026, 3, 19, 9, 0, tzinfo=UTC)
    fetched_at = datetime(2026, 3, 19, 9, 5, tzinfo=UTC)
    return NewsItem(
        source_name="Pipeline Metrics Test",
        source_url="https://example.com/pipeline",
        title=title,
        summary=summary,
        canonical_url=f"https://example.com/{url_hash}",
        url_hash=url_hash,
        market="us",
        language="en",
        sentiment_label=None,
        sentiment_score=None,
        published_at=published_at,
        fetched_at=fetched_at,
        effective_at=published_at,
        ingest_status="ingested",
    )


def _cleanup_news(url_hashes: list[str]) -> None:
    with SessionLocal() as session:
        news_ids = list(session.scalars(select(NewsItem.id).where(NewsItem.url_hash.in_(url_hashes))))
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
        session.commit()


def test_process_news_ids_counts_swallowed_crawl_errors_without_failing_batch() -> None:
    url_hashes = ["pipeline-crawl-error-metric"]
    _cleanup_news(url_hashes)

    with SessionLocal() as session:
        item = _make_news(
            title="Some company reports quarterly results",
            summary="Quarterly figures were released today.",
            url_hash=url_hashes[0],
        )
        session.add(item)
        session.commit()
        news_ids = [item.id]

    try:
        before = get_pipeline_error_counts()["crawl_error"]

        with SessionLocal() as session:
            summary = NewsSignalPipelineService(session).process_news_ids(news_ids)
            session.commit()

        after = get_pipeline_error_counts()["crawl_error"]

        # The crawl failure (network disabled by the autouse fixture) must be
        # counted exactly once for this single item...
        assert after == before + 1
        # ...while the batch itself still completes successfully (a single
        # item's crawl failure does not affect the rest of the pipeline).
        assert summary.processed_count == 1
    finally:
        _cleanup_news(url_hashes)
