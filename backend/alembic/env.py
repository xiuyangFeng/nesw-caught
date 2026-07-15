import os
import sys
from logging.config import fileConfig

# Add backend directory to sys.path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.db.base import Base

# Import all models to register them with Base.metadata
from app.models.article_content import ArticleContent
from app.models.feishu_notify_config import FeishuNotifyConfig
from app.models.llm_provider_config import LLMProviderConfig
from app.models.news_analysis_result import NewsAnalysisResult
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.notification_job import NotificationJob
from app.models.price_snapshot import PriceSnapshot
from app.models.source_health import SourceHealth
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.models.watchlist_item import WatchlistItem
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.models.x_account import XAccount
from app.models.x_post import XPost
from app.models.x_post_symbol_mention import XPostSymbolMention
from app.models.x_signal import XSignal
from app.models.x_signal_post_link import XSignalPostLink
from app.models.x_source_health import XSourceHealth

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set the sqlalchemy.url dynamically from app settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# disable_existing_loggers must stay False: migrations also run inside the app
# process (initialize_database() at startup / in tests) after app.* module
# loggers already exist, and the fileConfig default (True) would permanently
# silence all of them.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
