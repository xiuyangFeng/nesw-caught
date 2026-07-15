from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text

from app.core.config import get_settings
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.price_snapshot import PriceSnapshot
from app.workers.base_worker import BaseWorker

BATCH_SIZE = 1000


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DataCleanupWorker(BaseWorker):
    worker_name = "data_cleanup"

    def __init__(
        self,
        *,
        session_factory,
        cleanup_interval_seconds: float = 86400.0,
        vacuum_interval_seconds: float = 604800.0,
        news_item_retention_days: int = 180,
        article_content_retention_days: int = 90,
        price_snapshot_retention_days: int = 30,
        logger=None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.vacuum_interval_seconds = vacuum_interval_seconds
        self.news_item_retention_days = news_item_retention_days
        self.article_content_retention_days = article_content_retention_days
        self.price_snapshot_retention_days = price_snapshot_retention_days
        self._last_vacuum_at: datetime | None = None

    def get_interval(self) -> float:
        return self.cleanup_interval_seconds

    def do_cycle(self) -> int:
        deleted = 0
        deleted += self._delete_expired_news_items()
        deleted += self._delete_expired_article_content()
        deleted += self._delete_expired_price_snapshots()
        if self._should_run_vacuum():
            self._run_incremental_vacuum()
        return deleted

    def _delete_expired_news_items(self) -> int:
        cutoff = _utc_now() - timedelta(days=self.news_item_retention_days)
        with self.session_factory() as session:
            ids = list(
                session.scalars(
                    select(NewsItem.id)
                    .where(NewsItem.fetched_at < cutoff)
                    .order_by(NewsItem.fetched_at.asc(), NewsItem.id.asc())
                    .limit(BATCH_SIZE)
                )
            )
            if not ids:
                return 0
            session.execute(delete(NewsItem).where(NewsItem.id.in_(ids)))
            session.commit()
            return len(ids)

    def _delete_expired_article_content(self) -> int:
        cutoff = _utc_now() - timedelta(days=self.article_content_retention_days)
        with self.session_factory() as session:
            ids = list(
                session.scalars(
                    select(ArticleContent.id)
                    .where(ArticleContent.extracted_at.is_not(None))
                    .where(ArticleContent.extracted_at < cutoff)
                    .order_by(ArticleContent.extracted_at.asc(), ArticleContent.id.asc())
                    .limit(BATCH_SIZE)
                )
            )
            if not ids:
                return 0
            session.execute(delete(ArticleContent).where(ArticleContent.id.in_(ids)))
            session.commit()
            return len(ids)

    def _delete_expired_price_snapshots(self) -> int:
        cutoff = _utc_now() - timedelta(days=self.price_snapshot_retention_days)
        with self.session_factory() as session:
            ids = list(
                session.scalars(
                    select(PriceSnapshot.id)
                    .where(PriceSnapshot.fetched_at < cutoff)
                    .order_by(PriceSnapshot.fetched_at.asc(), PriceSnapshot.id.asc())
                    .limit(BATCH_SIZE)
                )
            )
            if not ids:
                return 0
            session.execute(delete(PriceSnapshot).where(PriceSnapshot.id.in_(ids)))
            session.commit()
            return len(ids)

    def _should_run_vacuum(self) -> bool:
        now = _utc_now()
        if self._last_vacuum_at is None:
            return True
        return (now - self._last_vacuum_at).total_seconds() >= self.vacuum_interval_seconds

    def _run_incremental_vacuum(self) -> None:
        with self.session_factory() as session:
            session.execute(text("PRAGMA incremental_vacuum"))
            session.commit()
        self._last_vacuum_at = _utc_now()


def build_data_cleanup_worker(session_factory) -> DataCleanupWorker:
    settings = get_settings()
    return DataCleanupWorker(
        session_factory=session_factory,
        cleanup_interval_seconds=settings.data_cleanup_interval_seconds,
        vacuum_interval_seconds=settings.data_cleanup_vacuum_interval_seconds,
        news_item_retention_days=settings.news_item_retention_days,
        article_content_retention_days=settings.article_content_retention_days,
        price_snapshot_retention_days=settings.price_snapshot_retention_days,
    )
