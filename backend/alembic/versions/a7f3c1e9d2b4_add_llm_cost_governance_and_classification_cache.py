"""add_llm_cost_governance_and_classification_cache

Revision ID: a7f3c1e9d2b4
Revises: c9d4f0a2b7e1
Create Date: 2026-07-13 10:00:00.000000

给 llm_provider_config 增加输入/输出单价与月度预算列，
并新增 llm_classification_cache 表用于缓存相同内容的分类结果。

本迁移位于 legacy 基线（ec84dec88ae5）之后，会在“legacy 库”路径下
针对 Base.metadata.create_all 出来的完整 schema 再次运行，因此每一步
都写成幂等的防御式操作（列/表已存在则跳过），与 c9d4f0a2b7e1 保持一致。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7f3c1e9d2b4'
down_revision: str | Sequence[str] | None = 'c9d4f0a2b7e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PRICE_COLUMNS = ('input_price_per_1k', 'output_price_per_1k', 'monthly_budget_usd')


def upgrade() -> None:
    """Upgrade schema (defensive / idempotent)."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if 'llm_provider_config' in tables:
        existing = {column['name'] for column in inspector.get_columns('llm_provider_config')}
        missing = [name for name in _PRICE_COLUMNS if name not in existing]
        if missing:
            with op.batch_alter_table('llm_provider_config', schema=None) as batch_op:
                for name in missing:
                    batch_op.add_column(sa.Column(name, sa.Float(), nullable=True))

    if 'llm_classification_cache' not in tables:
        op.create_table(
            'llm_classification_cache',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('content_hash', sa.String(length=64), nullable=False),
            sa.Column('result_json', sa.Text(), nullable=False),
            sa.Column('model_name', sa.String(length=128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            'ix_llm_classification_cache_content_hash',
            'llm_classification_cache',
            ['content_hash'],
            unique=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_llm_classification_cache_content_hash', table_name='llm_classification_cache')
    op.drop_table('llm_classification_cache')

    with op.batch_alter_table('llm_provider_config', schema=None) as batch_op:
        batch_op.drop_column('monthly_budget_usd')
        batch_op.drop_column('output_price_per_1k')
        batch_op.drop_column('input_price_per_1k')
