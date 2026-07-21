from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.config import Settings
from app.db.session import SessionLocal, engine
from app.repositories.notification_job_repository import NotificationJobRepository

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _cleanup_notification_jobs() -> None:
    inspector = inspect(engine)
    if "notification_job" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM notification_job"))


def _build_alembic_config() -> Config:
    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "backend" / "alembic"))
    return config


def test_enqueue_recovers_from_integrity_error_when_precheck_misses_concurrent_insert(
    monkeypatch,
) -> None:
    """并发窗口下"先查后插"的查重快路径可能读到旧快照(未命中)，但真正插入
    时会撞上 ux_notification_job_dedupe_key 唯一索引。repository 需要捕获
    该 IntegrityError 并回退为查询返回已存在的行，等价 upsert，调用方无感。
    """
    _cleanup_notification_jobs()

    with SessionLocal() as session:
        repo = NotificationJobRepository(session)
        dedupe_key = "race:concurrent-insert"

        existing = repo.enqueue(
            channel="feishu",
            event_type="analysis_result",
            payload={"news_id": 1},
            dedupe_key=dedupe_key,
        )

        original_get_by_dedupe_key = repo.get_by_dedupe_key
        calls = {"n": 0}

        def _miss_once(key: str):
            calls["n"] += 1
            if calls["n"] == 1:
                # 模拟查重快路径读到的是插入前的旧快照：未命中。
                return None
            return original_get_by_dedupe_key(key)

        monkeypatch.setattr(repo, "get_by_dedupe_key", _miss_once)

        recovered = repo.enqueue(
            channel="feishu",
            event_type="analysis_result",
            payload={"news_id": 1, "duplicate": True},
            dedupe_key=dedupe_key,
        )

        assert recovered.id == existing.id
        assert calls["n"] == 2  # 一次快路径未命中 + 一次冲突后的回退查询

        count = session.execute(
            text("SELECT COUNT(*) FROM notification_job WHERE dedupe_key = :key"),
            {"key": dedupe_key},
        ).scalar_one()
        assert count == 1

    # 冲突回滚只回退到 SAVEPOINT，外层 session 应仍可正常继续使用。
    with SessionLocal() as session:
        repo = NotificationJobRepository(session)
        again = repo.enqueue(
            channel="feishu",
            event_type="analysis_result",
            payload={"news_id": 2},
            dedupe_key="race:concurrent-insert-followup",
        )
        assert again.dedupe_key == "race:concurrent-insert-followup"


def test_migration_dedupes_historical_rows_and_enforces_unique_index(
    tmp_path, monkeypatch
) -> None:
    """构造一个停留在旧 head（d7f0a3b5c9e2）的库，其中含重复 dedupe_key 的
    历史行；升级到新迁移后：同 key 只保留 id 最大一条（其余置 NULL，不删
    行），唯一 key 不受影响，且唯一索引真正生效（重复插入报唯一冲突）。
    """
    db_path = tmp_path / "legacy_notification.db"
    legacy_engine = create_engine(f"sqlite:///{db_path}", future=True)

    with legacy_engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE notification_job (
                id INTEGER NOT NULL,
                channel VARCHAR(32) NOT NULL,
                event_type VARCHAR(64) NOT NULL,
                payload_json TEXT NOT NULL,
                status VARCHAR(16) NOT NULL,
                attempt_count INTEGER NOT NULL,
                next_retry_at DATETIME,
                dedupe_key VARCHAR(255),
                last_error TEXT,
                lease_until DATETIME,
                sent_at DATETIME,
                created_at DATETIME NOT NULL,
                lease_token VARCHAR(64),
                PRIMARY KEY (id)
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_notification_job_dedupe_key ON notification_job (dedupe_key)"
        )
        connection.execute(
            text(
                """
                INSERT INTO notification_job (
                    channel, event_type, payload_json, status, attempt_count,
                    dedupe_key, created_at
                ) VALUES (
                    :channel, :event_type, :payload_json, :status, :attempt_count,
                    :dedupe_key, :created_at
                )
                """
            ),
            [
                {
                    "channel": "news",
                    "event_type": "news_source_event",
                    "payload_json": "{}",
                    "status": "sent",
                    "attempt_count": 1,
                    "dedupe_key": "dup:key",
                    "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                },
                {
                    "channel": "news",
                    "event_type": "news_source_event",
                    "payload_json": "{}",
                    "status": "failed",
                    "attempt_count": 2,
                    "dedupe_key": "dup:key",
                    "created_at": datetime(2026, 1, 2, tzinfo=UTC),
                },
                {
                    "channel": "news",
                    "event_type": "news_source_event",
                    "payload_json": "{}",
                    "status": "pending",
                    "attempt_count": 0,
                    "dedupe_key": "dup:key",
                    "created_at": datetime(2026, 1, 3, tzinfo=UTC),
                },
                {
                    "channel": "feishu",
                    "event_type": "watchlist_alert",
                    "payload_json": "{}",
                    "status": "pending",
                    "attempt_count": 0,
                    "dedupe_key": "solo:key",
                    "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                },
            ],
        )

    test_settings = Settings(database_url=f"sqlite:///{db_path}", seed_demo_data=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: test_settings)

    alembic_cfg = _build_alembic_config()
    command.stamp(alembic_cfg, "d7f0a3b5c9e2")
    command.upgrade(alembic_cfg, "head")

    with legacy_engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, dedupe_key FROM notification_job ORDER BY id")
        ).fetchall()
        by_id = {row.id: row.dedupe_key for row in rows}

        assert len(rows) == 4  # 只置空 dedupe_key，不删行
        assert by_id[1] is None
        assert by_id[2] is None
        assert by_id[3] == "dup:key"  # 同 key 保留 id 最大的一条
        assert by_id[4] == "solo:key"  # 唯一 key 不受影响

        index_names = {
            row.name
            for row in connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='notification_job'"
                )
            ).fetchall()
        }
        assert "ux_notification_job_dedupe_key" in index_names
        assert "ix_notification_job_dedupe_key" not in index_names

    with legacy_engine.connect() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text(
                """
                INSERT INTO notification_job (
                    channel, event_type, payload_json, status, attempt_count,
                    dedupe_key, created_at
                ) VALUES (
                    'news', 'news_source_event', '{}', 'pending', 0,
                    'dup:key', :created_at
                )
                """
            ),
            {"created_at": datetime(2026, 1, 4, tzinfo=UTC)},
        )
