"""perf_batch_a_price_snapshot_symbol_fetched_index

Revision ID: c6e9a2b4d8f1
Revises: b5d8f1a3c7e2
Create Date: 2026-07-18 07:35:00.000000

性能优化批次 A：新增 ix_price_snapshot_symbol_fetched(symbol, fetched_at) 复合索引，
支撑 MarketRepository 的“每 symbol 最新一条”聚合查询（GROUP BY symbol + MAX(fetched_at)
后回表）以及回测的按 symbol 全历史读取。

与 b5d8f1a3c7e2 一致：纯索引增删直接执行 CREATE/DROP INDEX（不做
batch_alter_table 整表重建），并用 IF NOT EXISTS / IF EXISTS 保持幂等——
initialize_database 的 legacy 库修复路径会先按当前 metadata create_all
（索引已存在）再 alembic upgrade，非幂等写法会在该路径报 "already exists"。
"""
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c6e9a2b4d8f1'
down_revision: str | Sequence[str] | None = 'b5d8f1a3c7e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema (idempotent)."""
    op.execute(
        text('CREATE INDEX IF NOT EXISTS ix_price_snapshot_symbol_fetched ON price_snapshot (symbol, fetched_at)')
    )


def downgrade() -> None:
    """Downgrade schema (idempotent)."""
    op.execute(text('DROP INDEX IF EXISTS ix_price_snapshot_symbol_fetched'))
