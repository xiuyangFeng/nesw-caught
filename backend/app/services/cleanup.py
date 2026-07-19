from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, inspect as sa_inspect, select, text

from app.core.config import get_settings
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.price_snapshot import PriceSnapshot
from app.workers.base_worker import BaseWorker

BATCH_SIZE = 1000
DEFAULT_ARCHIVE_DIRNAME = "archive"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _default_archive_dir() -> Path:
    # backend/app/services/cleanup.py -> parents[2] == backend/
    return Path(__file__).resolve().parents[2] / "data" / DEFAULT_ARCHIVE_DIRNAME


def _model_to_jsonable_dict(instance: Any) -> dict[str, Any]:
    """把 ORM 实例的全部列字段导出为可 JSON 序列化的 dict（datetime -> isoformat）。"""
    data: dict[str, Any] = {}
    for column in sa_inspect(instance).mapper.column_attrs:
        value = getattr(instance, column.key)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.key] = value
    return data


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
        archive_dir: Path | str | None = None,
        logger=None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.vacuum_interval_seconds = vacuum_interval_seconds
        self.news_item_retention_days = news_item_retention_days
        self.article_content_retention_days = article_content_retention_days
        self.price_snapshot_retention_days = price_snapshot_retention_days
        self.archive_dir = Path(archive_dir) if archive_dir else _default_archive_dir()
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

    def _archive_rows(self, table_name: str, rows: list[Any]) -> None:
        """删除前归档：把待删行以 JSON Lines 追加写入按天分片的归档文件。

        只做“删前落一份可追溯文件”，不引入新表/不支持一键恢复导入——归档文件
        本身字段完整，需要时可人工读取/回填。
        """
        if not rows:
            return
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        date_str = _utc_now().strftime("%Y%m%d")
        archive_path = self.archive_dir / f"{table_name}_{date_str}.jsonl"
        with archive_path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(_model_to_jsonable_dict(row), ensure_ascii=False))
                fh.write("\n")

    def _delete_expired_news_items(self) -> int:
        cutoff = _utc_now() - timedelta(days=self.news_item_retention_days)
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(NewsItem)
                    .where(NewsItem.fetched_at < cutoff)
                    .order_by(NewsItem.fetched_at.asc(), NewsItem.id.asc())
                    .limit(BATCH_SIZE)
                )
            )
            if not rows:
                return 0
            self._archive_rows("news_item", rows)
            ids = [row.id for row in rows]
            session.execute(delete(NewsItem).where(NewsItem.id.in_(ids)))
            session.commit()
            return len(ids)

    def _delete_expired_article_content(self) -> int:
        cutoff = _utc_now() - timedelta(days=self.article_content_retention_days)
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(ArticleContent)
                    .where(ArticleContent.extracted_at.is_not(None))
                    .where(ArticleContent.extracted_at < cutoff)
                    .order_by(ArticleContent.extracted_at.asc(), ArticleContent.id.asc())
                    .limit(BATCH_SIZE)
                )
            )
            if not rows:
                return 0
            self._archive_rows("article_content", rows)
            ids = [row.id for row in rows]
            session.execute(delete(ArticleContent).where(ArticleContent.id.in_(ids)))
            session.commit()
            return len(ids)

    def _delete_expired_price_snapshots(self) -> int:
        cutoff = _utc_now() - timedelta(days=self.price_snapshot_retention_days)
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(PriceSnapshot)
                    .where(PriceSnapshot.fetched_at < cutoff)
                    .order_by(PriceSnapshot.fetched_at.asc(), PriceSnapshot.id.asc())
                    .limit(BATCH_SIZE)
                )
            )
            if not rows:
                return 0
            self._archive_rows("price_snapshot", rows)
            ids = [row.id for row in rows]
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
        archive_dir=Path(settings.data_archive_dir) if settings.data_archive_dir else None,
    )
