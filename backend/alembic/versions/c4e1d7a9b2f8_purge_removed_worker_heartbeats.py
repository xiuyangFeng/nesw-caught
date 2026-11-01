"""purge heartbeats of removed workers (focus redesign P1)

量化盘后调度（``quant_scheduler``）与 X 健康探针（``x_health_probe``）已随 P1 下线，
但它们在 ``worker_runtime_status`` 里的心跳行仍在，系统健康页会因心跳不再更新而
永久报 ``worker.heartbeat_timeout``。这里删除这两行。

心跳行属于运行时状态（worker 启动后会自行 upsert），downgrade 无需恢复。

Revision ID: c4e1d7a9b2f8
Revises: c3b8f0e2a5d6
Create Date: 2026-11-01 06:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4e1d7a9b2f8"
down_revision: str | Sequence[str] | None = "c3b8f0e2a5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REMOVED_WORKERS: tuple[str, ...] = ("quant_scheduler", "x_health_probe")


def upgrade() -> None:
    bind = op.get_bind()
    if "worker_runtime_status" not in sa.inspect(bind).get_table_names():
        return
    worker_runtime_status = sa.table("worker_runtime_status", sa.column("worker_name", sa.String()))
    bind.execute(
        sa.delete(worker_runtime_status).where(worker_runtime_status.c.worker_name.in_(REMOVED_WORKERS))
    )


def downgrade() -> None:
    pass
