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
