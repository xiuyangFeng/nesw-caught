"""聚焦改造 P1 迁移测试：已下线 worker 的心跳残留必须在升级时被清除。

量化调度与 X 健康探针下线后，它们在 ``worker_runtime_status`` 的心跳行不再更新，
系统健康页会永久报 ``worker.heartbeat_timeout``。迁移 ``c4e1d7a9b2f8`` 负责删掉这些行，
且不能误删仍在运行的 worker。
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from app.core.config import Settings
from app.db.base import Base

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "backend" / "alembic"))
    config.attributes["configure_logger"] = False
    return config


def test_upgrade_purges_heartbeats_of_removed_workers(tmp_path: Path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'p1.db'}"
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    now = datetime.now(UTC).isoformat()
    with engine.begin() as connection:
        for name in ("quant_scheduler", "x_health_probe", "news_ingest_scheduler"):
            connection.execute(
                text(
                    "INSERT INTO worker_runtime_status "
                    "(worker_name, status, last_heartbeat_at, cycle_count, success_count, failure_count, "
                    "last_quotes_count) VALUES (:name, 'ok', :now, 0, 0, 0, 0)"
                ),
                {"name": name, "now": now},
            )
    engine.dispose()

    test_settings = Settings(database_url=db_url, seed_demo_data=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: test_settings)
    config = _alembic_config()
    command.stamp(config, "c3b8f0e2a5d6")
    command.upgrade(config, "head")

    engine = create_engine(db_url)
    with engine.connect() as connection:
        remaining = {row[0] for row in connection.execute(text("SELECT worker_name FROM worker_runtime_status"))}
    engine.dispose()

    assert remaining == {"news_ingest_scheduler"}
