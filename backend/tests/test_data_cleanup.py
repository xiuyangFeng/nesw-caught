from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.article_content import ArticleContent
from app.models.llm_classification_cache import LLMClassificationCache
from app.models.llm_token_usage import LLMTokenUsage
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


def test_data_cleanup_worker_archives_and_deletes_expired_llm_token_usage(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    archive_dir = tmp_path / "archive"
    worker = DataCleanupWorker(
        session_factory=SessionLocal,
        cleanup_interval_seconds=60.0,
        vacuum_interval_seconds=604800.0,
        llm_token_usage_retention_days=90,
        llm_classification_cache_retention_days=30,
        archive_dir=archive_dir,
    )

    with SessionLocal() as session:
        expired = LLMTokenUsage(
            model_name="deepseek-chat",
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            operation_type="analysis",
            created_at=now - timedelta(days=100),
        )
        fresh = LLMTokenUsage(
            model_name="deepseek-chat",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            operation_type="analysis",
            created_at=now - timedelta(days=1),
        )
        session.add_all([expired, fresh])
        session.commit()
        expired_id = expired.id
        fresh_id = fresh.id

    deleted = worker.do_cycle()
    assert deleted >= 1

    date_str = now.strftime("%Y%m%d")
    archive_path = archive_dir / f"llm_token_usage_{date_str}.jsonl"
    assert archive_path.exists()
    archived_records = [
        json.loads(line) for line in archive_path.read_text(encoding="utf-8").splitlines() if line
    ]
    matching = [record for record in archived_records if record["id"] == expired_id]
    assert len(matching) == 1
    assert matching[0]["model_name"] == "deepseek-chat"

    with SessionLocal() as session:
        assert session.scalar(select(LLMTokenUsage).where(LLMTokenUsage.id == expired_id)) is None
        assert session.scalar(select(LLMTokenUsage).where(LLMTokenUsage.id == fresh_id)) is not None


def test_data_cleanup_worker_deletes_expired_llm_classification_cache_without_archive(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC)
    archive_dir = tmp_path / "archive"
    worker = DataCleanupWorker(
        session_factory=SessionLocal,
        cleanup_interval_seconds=60.0,
        vacuum_interval_seconds=604800.0,
        llm_token_usage_retention_days=90,
        llm_classification_cache_retention_days=30,
        archive_dir=archive_dir,
    )

    with SessionLocal() as session:
        expired = LLMClassificationCache(
            content_hash="expired-hash-cleanup-test",
            result_json='{"label": "old"}',
            model_name="deepseek-chat",
            created_at=now - timedelta(days=40),
        )
        fresh = LLMClassificationCache(
            content_hash="fresh-hash-cleanup-test",
            result_json='{"label": "new"}',
            model_name="deepseek-chat",
            created_at=now - timedelta(days=1),
        )
        session.add_all([expired, fresh])
        session.commit()
        expired_id = expired.id
        fresh_id = fresh.id

    deleted = worker.do_cycle()
    assert deleted >= 1

    date_str = now.strftime("%Y%m%d")
    archive_path = archive_dir / f"llm_classification_cache_{date_str}.jsonl"
    assert not archive_path.exists()

    with SessionLocal() as session:
        assert (
            session.scalar(
                select(LLMClassificationCache).where(LLMClassificationCache.id == expired_id)
            )
            is None
        )
        assert (
            session.scalar(select(LLMClassificationCache).where(LLMClassificationCache.id == fresh_id))
            is not None
        )


def test_data_cleanup_worker_retention_zero_matches_existing_table_semantics(tmp_path: Path) -> None:
    """retention_days=0 时新表与既有表(price_snapshot)语义一致:cutoff=now,不做“禁用”特判。"""
    now = datetime.now(UTC)
    archive_dir = tmp_path / "archive"
    worker = DataCleanupWorker(
        session_factory=SessionLocal,
        cleanup_interval_seconds=60.0,
        vacuum_interval_seconds=604800.0,
        price_snapshot_retention_days=0,
        llm_token_usage_retention_days=0,
        llm_classification_cache_retention_days=0,
        archive_dir=archive_dir,
    )

    with SessionLocal() as session:
        price_snapshot = PriceSnapshot(
            symbol="000001.SZ",
            market="cn",
            price=10.0,
            change_percent=0.0,
            fetched_at=now - timedelta(seconds=1),
        )
        token_usage = LLMTokenUsage(
            model_name="deepseek-chat",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            operation_type="analysis",
            created_at=now - timedelta(seconds=1),
        )
        cache_entry = LLMClassificationCache(
            content_hash="retention-zero-hash-cleanup-test",
            result_json='{"label": "zero"}',
            model_name="deepseek-chat",
            created_at=now - timedelta(seconds=1),
        )
        session.add_all([price_snapshot, token_usage, cache_entry])
        session.commit()
        price_id = price_snapshot.id
        usage_id = token_usage.id
        cache_id = cache_entry.id

    worker.do_cycle()

    with SessionLocal() as session:
        assert session.scalar(select(PriceSnapshot).where(PriceSnapshot.id == price_id)) is None
        assert session.scalar(select(LLMTokenUsage).where(LLMTokenUsage.id == usage_id)) is None
        assert (
            session.scalar(select(LLMClassificationCache).where(LLMClassificationCache.id == cache_id))
            is None
        )
