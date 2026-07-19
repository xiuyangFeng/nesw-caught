from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.price_snapshot import PriceSnapshot
from app.services.cleanup import DataCleanupWorker


def test_data_cleanup_worker_deletes_expired_rows_in_batches() -> None:
    now = datetime.now(UTC)
    worker = DataCleanupWorker(
        session_factory=SessionLocal,
        cleanup_interval_seconds=60.0,
        vacuum_interval_seconds=604800.0,
        news_item_retention_days=180,
        article_content_retention_days=90,
        price_snapshot_retention_days=30,
    )

    with SessionLocal() as session:
        news_item = NewsItem(
            source_name="Cleanup Test",
            source_url="https://example.com/cleanup",
            title="Expired news",
            summary="cleanup",
            canonical_url="https://example.com/cleanup-news",
            url_hash="test-cleanup-news",
            market="us",
            language="en",
            sentiment_label=None,
            sentiment_score=None,
            published_at=now - timedelta(days=200),
            fetched_at=now - timedelta(days=200),
            ingest_status="ingested",
        )
        session.add(news_item)
        session.flush()
        session.add(
            ArticleContent(
                news_id=news_item.id,
                content_text="expired body",
                extract_status="success",
                extracted_at=now - timedelta(days=120),
            )
        )
        session.add(
            PriceSnapshot(
                symbol="600519.SH",
                market="cn",
                price=100.0,
                change_percent=0.0,
                fetched_at=now - timedelta(days=60),
            )
        )
        session.commit()
        news_id = news_item.id

    deleted = worker.do_cycle()
    assert deleted >= 2

    with SessionLocal() as session:
        assert session.scalar(select(NewsItem).where(NewsItem.id == news_id)) is None
        assert session.scalar(select(ArticleContent).where(ArticleContent.news_id == news_id)) is None
        assert session.scalar(select(PriceSnapshot).where(PriceSnapshot.symbol == "600519.SH")) is None


def test_data_cleanup_worker_archives_rows_before_deleting(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    archive_dir = tmp_path / "archive"
    worker = DataCleanupWorker(
        session_factory=SessionLocal,
        cleanup_interval_seconds=60.0,
        vacuum_interval_seconds=604800.0,
        news_item_retention_days=180,
        article_content_retention_days=90,
        price_snapshot_retention_days=30,
        archive_dir=archive_dir,
    )

    with SessionLocal() as session:
        news_item = NewsItem(
            source_name="Archive Test",
            source_url="https://example.com/archive",
            title="Expired news for archive",
            summary="archive-test",
            canonical_url="https://example.com/archive-news",
            url_hash="test-archive-news",
            market="us",
            language="en",
            sentiment_label=None,
            sentiment_score=None,
            published_at=now - timedelta(days=200),
            fetched_at=now - timedelta(days=200),
            ingest_status="ingested",
        )
        session.add(news_item)
        session.commit()
        news_id = news_item.id

    deleted = worker.do_cycle()
    assert deleted >= 1

    date_str = now.strftime("%Y%m%d")
    archive_path = archive_dir / f"news_item_{date_str}.jsonl"
    assert archive_path.exists()

    archived_records = [
        json.loads(line) for line in archive_path.read_text(encoding="utf-8").splitlines() if line
    ]
    matching = [record for record in archived_records if record["id"] == news_id]
    assert len(matching) == 1
    assert matching[0]["title"] == "Expired news for archive"
    assert matching[0]["canonical_url"] == "https://example.com/archive-news"

    with SessionLocal() as session:
        assert session.scalar(select(NewsItem).where(NewsItem.id == news_id)) is None
