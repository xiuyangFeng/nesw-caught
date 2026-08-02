"""add_market_index_config

Revision ID: e5f9a2c4b7d1
Revises: d4b7e1f0c3a6
Create Date: 2026-08-02 09:00:00.000000

新增 market_index_config 表（市场总览的指数/板块代理 ETF 配置）。

本迁移位于 legacy 基线（ec84dec88ae5）之后，会在“legacy 库”路径下
针对 Base.metadata.create_all 出来的完整 schema 再次运行，因此写成
幂等的防御式操作（表已存在则跳过），与 a7f3c1e9d2b4 保持一致。
迁移里不 seed 数据：默认指数清单由应用层负责（表为空时
MarketOverviewService 回落内置默认清单）。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5f9a2c4b7d1'
down_revision: str | Sequence[str] | None = 'd4b7e1f0c3a6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema (defensive / idempotent)."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if 'market_index_config' not in inspector.get_table_names():
        op.create_table(
            'market_index_config',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('symbol', sa.String(length=32), nullable=False),
            sa.Column('market', sa.String(length=16), nullable=False),
            sa.Column('display_name', sa.String(length=64), nullable=False),
            sa.Column('kind', sa.String(length=16), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('symbol', 'market', name='uq_market_index_config_symbol_market'),
        )
        op.create_index(
            'ix_market_index_config_market',
            'market_index_config',
            ['market'],
        )
        op.create_index(
            'ix_market_index_config_market_enabled_sort',
            'market_index_config',
            ['market', 'enabled', 'sort_order'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_market_index_config_market_enabled_sort', table_name='market_index_config')
    op.drop_index('ix_market_index_config_market', table_name='market_index_config')
    op.drop_table('market_index_config')
