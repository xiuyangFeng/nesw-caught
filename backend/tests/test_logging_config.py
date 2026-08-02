"""Regression tests for logging behaviour around database initialization.

Production startup order (app/main.py) is: import app modules (which creates
their module-level loggers) -> initialize_database() -> serve. Alembic's
env.py calls logging.config.fileConfig(), whose default
disable_existing_loggers=True silently disables every already-created app.*
logger, so all later logger.warning()/exception() calls emit nothing.
"""

import logging

from app.db.initializer import initialize_database


def test_initialize_database_keeps_existing_app_loggers_enabled():
    probe = logging.getLogger("app.services.ingestion.fetcher")
    probe.disabled = False

    # Re-running on an already-migrated database takes the plain
    # "upgrade to head" path, which executes alembic/env.py -> fileConfig().
    initialize_database()

    assert not probe.disabled, (
        "alembic env.py fileConfig() disabled pre-existing app loggers; "
        "it must pass disable_existing_loggers=False"
    )


def test_initialize_database_does_not_touch_root_handlers():
    """2026-08 重构回归：initializer 传 configure_logger=False 后，应用进程内跑
    alembic 不得改动 root logger 的 handler 集合与等级（此前 alembic.ini 的
    fileConfig 会把 root 压到 WARNING 并塞入自己的 console handler，
    pipeline_worker_main 曾靠事后摘 handler 补救——该补救逻辑已删除，
    这里保证前提长期成立）。"""
    root_logger = logging.getLogger()
    handlers_before = list(root_logger.handlers)
    level_before = root_logger.level

    initialize_database()

    assert root_logger.handlers == handlers_before, (
        "initialize_database() 改动了 root handler 集合；alembic fileConfig "
        "可能重新接管了日志配置（configure_logger attribute 失效？）"
    )
    assert root_logger.level == level_before
