from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from app.core.config import get_settings

settings = get_settings()

def _looks_like_memory_sqlite(url: str) -> bool:
    """形如 `sqlite:///:memory:` / `sqlite://` / `...?mode=memory` 的内存库判定。

    内存库的每条新连接都是一个全新的空库，绝不能放进多连接的 QueuePool——否则
    建表的连接和查询的连接会看到不同的库（测试会直接崩）。这类 URL 必须走
    StaticPool（全进程共享同一条 DBAPI 连接）以保住既有语义。
    """
    if not url.startswith("sqlite"):
        return False
    return (
        ":memory:" in url
        or "mode=memory" in url
        or url in {"sqlite://", "sqlite+pysqlite://"}
    )


_is_sqlite = settings.database_url.startswith("sqlite")
_is_memory_sqlite = _looks_like_memory_sqlite(settings.database_url)

# SQLite: 设置 busy timeout,避免读写短暂交叠时直接抛 "database is locked"。
# check_same_thread=False:连接会在 anyio 线程池的多个线程之间被复用(池化的
# 前提),不关掉 sqlite3 的同线程校验就会在跨线程复用时抛 ProgrammingError。
# 并发安全由上面的 busy_timeout + WAL + 每次只有一个 Session 持有一条连接保证。
_connect_args: dict[str, object] = (
    {"timeout": 30, "check_same_thread": False} if _is_sqlite else {}
)

if _is_memory_sqlite:
    _engine_kwargs: dict[str, object] = {"poolclass": StaticPool}
else:
    # 显式配置 QueuePool。此前未配置,SQLAlchemy 对文件型 SQLite 默认
    # pool_size=5 / max_overflow=10 —— 总共只有 15 条连接,却要同时服务
    # anyio 线程池里的全部同步 def 路由 + 6 个后台 worker。池耗尽时请求会
    # 静默阻塞到 pool_timeout(默认 30s)才报错,表现为"点一下几秒没反应"。
    _engine_kwargs = {
        "poolclass": QueuePool,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        # 池满时宁可较快失败让上层重试,也不要静默卡满 30 秒。
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
        # 取出连接前先探活,避免拿到已被回收/失效的连接直接报错。
        "pool_pre_ping": True,
    }

engine = create_engine(
    settings.database_url,
    future=True,
    connect_args=_connect_args,
    **_engine_kwargs,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if _is_sqlite:
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
        # WAL 自动 checkpoint 阈值。此前未设置(SQLite 默认 1000 页,但持续存在的
        # 读连接会一直饿死 checkpoint),实测 app.db 8.8MB 而 app.db-wal 长到
        # 6.3MB —— 每次读都要先扫这个巨大的 WAL index,形成全局读放大。
        cursor.execute(f"PRAGMA wal_autocheckpoint={settings.sqlite_wal_autocheckpoint_pages}")
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
