from __future__ import annotations

import sqlite3
from pathlib import Path

from app.services.backup import BackupWorker, sqlite_path_from_url


def _make_source_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO demo (value) VALUES ('hello')")
        conn.commit()
    finally:
        conn.close()


def test_backup_worker_creates_readable_backup(tmp_path: Path) -> None:
    source_db_path = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    _make_source_db(source_db_path)

    worker = BackupWorker(
        session_factory=lambda: None,
        source_db_path=source_db_path,
        backup_dir=backup_dir,
        backup_interval_seconds=86400.0,
        backup_retention_count=3,
    )

    result = worker.do_cycle()
    assert result == 1

    backups = list(backup_dir.glob("source_*.db"))
    assert len(backups) == 1

    conn = sqlite3.connect(str(backups[0]))
    try:
        rows = conn.execute("SELECT value FROM demo").fetchall()
    finally:
        conn.close()
    assert rows == [("hello",)]


def test_backup_worker_prunes_old_backups(tmp_path: Path) -> None:
    source_db_path = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    _make_source_db(source_db_path)

    worker = BackupWorker(
        session_factory=lambda: None,
        source_db_path=source_db_path,
        backup_dir=backup_dir,
        backup_interval_seconds=86400.0,
        backup_retention_count=2,
    )

    for _ in range(4):
        worker.do_cycle()

    backups = list(backup_dir.glob("source_*.db"))
    assert len(backups) <= 2


def test_sqlite_path_from_url_parses_sqlite_urls() -> None:
    assert sqlite_path_from_url("sqlite:////abs/path/app.db") == Path("/abs/path/app.db")
    assert sqlite_path_from_url("postgresql://user:pw@host/db") is None
