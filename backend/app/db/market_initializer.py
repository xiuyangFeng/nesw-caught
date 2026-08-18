"""独立行情库启动初始化（与 app.db 物理隔离）。"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from alembic import command
from app.db.market_base import MarketBase
from app.db.market_session import market_engine
from app.models.market_data import (  # noqa: F401
    DailyBar,
    FundFlowDaily,
    IndexDailyBar,
    TradeCalendar,
)

logger = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _build_alembic_config() -> Config:
    ini_path = _REPO_ROOT / "alembic_market.ini"
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(_REPO_ROOT / "backend" / "alembic_market"))
    config.attributes["configure_logger"] = False
    return config


def initialize_market_database() -> None:
    inspector = inspect(market_engine)
    application_tables = set(inspector.get_table_names()) - {"alembic_version_market"}
    alembic_cfg = _build_alembic_config()

    with market_engine.connect() as connection:
        current = MigrationContext.configure(
            connection, opts={"version_table": "alembic_version_market"}
        ).get_current_revision()

    if not application_tables:
        logger.info("Fresh market_data.db: creating schema and stamping Alembic head.")
        MarketBase.metadata.create_all(bind=market_engine)
        command.stamp(alembic_cfg, "head")
    elif current is None:
        logger.info("Unstamped market_data.db: create_all then stamp head.")
        MarketBase.metadata.create_all(bind=market_engine)
        command.stamp(alembic_cfg, "head")
    else:
        logger.info("Existing market_data.db: upgrading Alembic to head.")
        command.upgrade(alembic_cfg, "head")
