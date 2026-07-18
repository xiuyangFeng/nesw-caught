from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
# SQLite: 设置 busy timeout,避免读写短暂交叠时直接抛 "database is locked"。
_connect_args = {"timeout": 30} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, future=True, connect_args=_connect_args)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        # auto_vacuum 只在“空库”状态下设置才会生效，且必须排在 journal_mode=WAL
        # 之前——WAL 会先落一次写入，令库不再是空库，导致该 pragma 变成空操作。
        # 新库从第一次连接起就是 incremental 模式，才能让 cleanup.py 的
        # PRAGMA incremental_vacuum 真正回收空间；既有库需要 VACUUM 才能切换模式，
        # 见 alembic revision f3a7c1e9b5d2。
        cursor.execute("PRAGMA auto_vacuum=INCREMENTAL")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI 请求级会话依赖：统一事务边界。

    - 请求成功结束时 commit（repository 层只 flush，提交权收口在这里）；
    - 请求抛出异常（含 HTTPException）时 rollback，保证组合写操作原子回滚；
    - 非请求上下文（worker/scheduler/后台线程）不经过本依赖，需自行 commit。
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
