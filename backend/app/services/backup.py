from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.workers.base_worker import BaseWorker

DEFAULT_BACKUP_DIRNAME = "backups"
_SQLITE_URL_PREFIX = "sqlite:///"


def _default_backup_dir() -> Path:
    # backend/app/services/backup.py -> parents[2] == backend/
    return Path(__file__).resolve().parents[2] / "data" / DEFAULT_BACKUP_DIRNAME


def sqlite_path_from_url(database_url: str) -> Path | None:
    """从 SQLAlchemy 的 sqlite URL 中解析出文件路径；非 sqlite（如未来切 Postgres）返回 None。"""
    if not database_url.startswith(_SQLITE_URL_PREFIX):
        return None
    return Path(database_url[len(_SQLITE_URL_PREFIX) :])


class BackupWorker(BaseWorker):
    """周期性对 SQLite 数据库文件做在线备份。

    使用 sqlite3.Connection.backup() 官方 API（而非直接复制文件），避免在写入
    进行中的时刻复制出损坏/不一致的备份文件；该 API 会正确处理 WAL 模式下的
    并发读写。备份文件按时间戳命名，只保留最近 N 份，超出的旧备份会被删除。
    """

    worker_name = "sqlite_backup"

    def __init__(
        self,
        *,
        session_factory,
        source_db_path: Path | str,
        backup_dir: Path | str,
        backup_interval_seconds: float = 86400.0,
        backup_retention_count: int = 7,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.source_db_path = Path(source_db_path)
        self.backup_dir = Path(backup_dir)
        self.backup_interval_seconds = backup_interval_seconds
        self.backup_retention_count = max(1, backup_retention_count)

    def get_interval(self) -> float:
        return self.backup_interval_seconds

    def do_cycle(self) -> int:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = self._make_backup()
        self._prune_old_backups()
        return 1 if backup_path is not None else 0

    def _make_backup(self) -> Path | None:
        if not self.source_db_path.exists():
            self.logger.warning(
                "Backup skipped: source db '%s' does not exist", self.source_db_path
            )
            return None
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{self.source_db_path.stem}_{timestamp}.db"
        source_conn = sqlite3.connect(str(self.source_db_path))
        try:
            dest_conn = sqlite3.connect(str(backup_path))
            try:
                source_conn.backup(dest_conn)
            finally:
                dest_conn.close()
        finally:
            source_conn.close()
        self.logger.info("SQLite backup written to %s", backup_path)
        return backup_path

    def _prune_old_backups(self) -> None:
        pattern = f"{self.source_db_path.stem}_*.db"
        backups = sorted(
            self.backup_dir.glob(pattern),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for stale in backups[self.backup_retention_count :]:
            try:
                stale.unlink()
            except OSError:
                self.logger.exception("Failed to remove stale backup %s", stale)


def build_backup_worker(session_factory) -> BackupWorker | None:
    """按 settings 构建 BackupWorker；若 database_url 不是 sqlite（未来切换 Postgres 等），
    在线备份策略不再适用，返回 None，调用方应跳过启动。
    """
    settings = get_settings()
    source_db_path = sqlite_path_from_url(settings.database_url)
    if source_db_path is None:
        return None
    backup_dir = Path(settings.backup_dir) if settings.backup_dir else _default_backup_dir()
    return BackupWorker(
        session_factory=session_factory,
        source_db_path=source_db_path,
        backup_dir=backup_dir,
        backup_interval_seconds=settings.backup_interval_seconds,
        backup_retention_count=settings.backup_retention_count,
    )
