from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from app.core.config import get_settings
from app.db.session import _looks_like_memory_sqlite

settings = get_settings()

_is_sqlite = settings.market_database_url.startswith("sqlite")
_is_memory_sqlite = _looks_like_memory_sqlite(settings.market_database_url)
_connect_args: dict[str, object] = (
    {"timeout": 30, "check_same_thread": False} if _is_sqlite else {}
)

if _is_memory_sqlite:
    _engine_kwargs: dict[str, object] = {"poolclass": StaticPool}
else:
    _engine_kwargs = {
        "poolclass": QueuePool,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
        "pool_pre_ping": True,
    }

market_engine = create_engine(
    settings.market_database_url,
    future=True,
    connect_args=_connect_args,
    **_engine_kwargs,
)


@event.listens_for(market_engine, "connect")
def set_market_sqlite_pragma(dbapi_connection, connection_record):
    if _is_sqlite:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


MarketSessionLocal = sessionmaker(
    bind=market_engine, autoflush=False, autocommit=False, class_=Session
)


def get_market_session() -> Generator[Session, None, None]:
    session = MarketSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
