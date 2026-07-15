"""Database startup initialization.

Schema evolution is single-tracked through Alembic:

- Fresh database (no application tables yet): ``Base.metadata.create_all``
  followed by ``alembic stamp head`` — the standard fast path for brand-new
  databases.
- Existing database that was never stamped (created by the legacy
  ``create_all``-based initializer): ``create_all`` to add any tables that
  are missing, ``alembic stamp`` to the legacy baseline revision, then
  ``alembic upgrade head`` so repair migrations newer than the baseline
  (e.g. the source_health market backfill) still run.
- Existing stamped database: ``alembic upgrade head`` only.

Any migration failure raises and aborts startup (fail fast) so that
``alembic_version`` can never silently drift from the actual schema.

Demo seed data lives in ``scripts/seed_demo_data.py`` and is only applied
when the ``seed_demo_data`` setting is true.
"""
import logging
from importlib import util as importlib_util
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from alembic import command
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine

# Import all models so Base.metadata registers every table for create_all.
from app.models.article_content import ArticleContent  # noqa: F401
from app.models.feishu_notify_config import FeishuNotifyConfig  # noqa: F401
from app.models.llm_classification_cache import LLMClassificationCache  # noqa: F401
from app.models.llm_provider_config import LLMProviderConfig  # noqa: F401
from app.models.llm_token_usage import LLMTokenUsage  # noqa: F401
from app.models.news_analysis_result import NewsAnalysisResult  # noqa: F401
from app.models.news_item import NewsItem  # noqa: F401
from app.models.news_stock_mention import NewsStockMention  # noqa: F401
from app.models.notification_job import NotificationJob  # noqa: F401
from app.models.price_snapshot import PriceSnapshot  # noqa: F401
from app.models.source_health import SourceHealth  # noqa: F401
from app.models.topic_cluster import TopicCluster  # noqa: F401
from app.models.topic_news_link import TopicNewsLink  # noqa: F401
from app.models.watchlist_item import WatchlistItem  # noqa: F401
from app.models.worker_runtime_status import WorkerRuntimeStatus  # noqa: F401
from app.models.x_account import XAccount  # noqa: F401
from app.models.x_post import XPost  # noqa: F401
from app.models.x_post_symbol_mention import XPostSymbolMention  # noqa: F401
from app.models.x_signal import XSignal  # noqa: F401
from app.models.x_signal_post_link import XSignalPostLink  # noqa: F401
from app.models.x_source_health import XSourceHealth  # noqa: F401

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Databases created by the legacy create_all-based initializer carry no
# alembic_version table. Their ORM tables already match what the historical
# migration chain up to this revision produces (the old initializer ran
# create_all and hand-written repairs, then stamped head), so we baseline
# them here and let `upgrade head` run only the newer repair migrations.
_LEGACY_BASELINE_REVISION = "ec84dec88ae5"


def _build_alembic_config() -> Config:
    ini_path = _REPO_ROOT / "alembic.ini"
    config = Config(str(ini_path)) if ini_path.exists() else Config("alembic.ini")

    script_location = _REPO_ROOT / "backend" / "alembic"
    if not script_location.exists():
        script_location = Path(__file__).resolve().parents[2] / "alembic"
    config.set_main_option("script_location", str(script_location))
    return config


def _current_alembic_revision() -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def initialize_database() -> None:
    inspector = inspect(engine)
    application_tables = set(inspector.get_table_names()) - {"alembic_version"}
    alembic_cfg = _build_alembic_config()

    if not application_tables:
        logger.info("Fresh database detected: creating schema and stamping Alembic head.")
        Base.metadata.create_all(bind=engine)
        command.stamp(alembic_cfg, "head")
    elif _current_alembic_revision() is None:
        logger.info(
            "Legacy database without Alembic baseline detected: creating missing tables, "
            "stamping %s, then upgrading to head.",
            _LEGACY_BASELINE_REVISION,
        )
        Base.metadata.create_all(bind=engine)
        command.stamp(alembic_cfg, _LEGACY_BASELINE_REVISION)
        command.upgrade(alembic_cfg, "head")
    else:
        logger.info("Existing database detected: running Alembic upgrade to head.")
        command.upgrade(alembic_cfg, "head")

    if get_settings().seed_demo_data:
        _apply_demo_seeds()


def _apply_demo_seeds() -> None:
    try:
        _load_seed_module().seed_demo_data()
    except Exception as exc:
        logger.warning(
            "Demo seed step skipped: %s (likely concurrent initialization already "
            "populated seed data, or scripts/seed_demo_data.py is unavailable).",
            exc,
        )


def _load_seed_module():
    seed_path = _REPO_ROOT / "scripts" / "seed_demo_data.py"
    spec = importlib_util.spec_from_file_location("news_caught_seed_demo_data", seed_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load seed module from {seed_path}")
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
