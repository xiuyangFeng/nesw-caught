"""set_sqlite_auto_vacuum_incremental

Revision ID: f3a7c1e9b5d2
Revises: e2b4c6d8f0a1
Create Date: 2026-07-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f3a7c1e9b5d2'
down_revision: str | Sequence[str] | None = 'e2b4c6d8f0a1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """一次性迁移：把既有库切换到 incremental auto_vacuum 模式。

    SQLite 的 auto_vacuum 模式在建库时固定，仅设置 PRAGMA 对已有数据的库是空操作，
    必须紧跟一次 VACUUM 才能让新模式生效（见 backend/app/db/session.py 里
    set_sqlite_pragma 的注释）。VACUUM 会短暂拿独占锁，属于一次性代价，可接受。
    新建的库从 session.py 的连接 pragma 起就是 incremental 模式，这里做幂等检查，
    已经是 incremental（返回值 2）时跳过，避免重复 VACUUM。
    """
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    current_mode = bind.exec_driver_sql("PRAGMA auto_vacuum").scalar()
    if current_mode != 2:
        bind.exec_driver_sql("PRAGMA auto_vacuum=INCREMENTAL")
        bind.exec_driver_sql("VACUUM")


def downgrade() -> None:
    """不可逆：SQLite 切回 full/none 模式同样需要 VACUUM，且会丢失 incremental
    回收带来的空间收益，此处不做自动降级，如需还原请手工执行
    `PRAGMA auto_vacuum=NONE` 后接 `VACUUM`。"""
    pass
