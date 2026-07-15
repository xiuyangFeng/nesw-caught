"""add_watchlist_position_and_cost

Revision ID: b8e4d7f2a9c1
Revises: a7f3c1e9d2b4
Create Date: 2026-07-13 12:00:00.000000

给 watchlist_item 表增加持仓/组合视图所需的两列：
- position_size（Float，可空）：该自选股的持仓数量；
- average_cost（Float，可空）：该自选股的平均建仓成本。

本迁移位于 legacy 基线（ec84dec88ae5）之后，会在“legacy 库”路径下
针对 Base.metadata.create_all 出来的完整 schema 再次运行，因此每一步
都写成幂等的防御式操作（列已存在则跳过），与 a7f3c1e9d2b4 / c9d4f0a2b7e1
保持一致。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8e4d7f2a9c1'
down_revision: str | Sequence[str] | None = 'a7f3c1e9d2b4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_POSITION_COLUMNS = ('position_size', 'average_cost')


def upgrade() -> None:
    """Upgrade schema (defensive / idempotent)."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if 'watchlist_item' in tables:
        existing = {column['name'] for column in inspector.get_columns('watchlist_item')}
        missing = [name for name in _POSITION_COLUMNS if name not in existing]
        if missing:
            with op.batch_alter_table('watchlist_item', schema=None) as batch_op:
                for name in missing:
                    batch_op.add_column(sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('watchlist_item', schema=None) as batch_op:
        batch_op.drop_column('average_cost')
        batch_op.drop_column('position_size')
