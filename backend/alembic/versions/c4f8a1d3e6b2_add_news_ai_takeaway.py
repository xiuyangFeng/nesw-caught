"""add_news_ai_takeaway

Revision ID: c4f8a1d3e6b2
Revises: b8e4d7f2a9c1
Create Date: 2026-07-15 12:00:00.000000

给 news_item 表增加 AI 一句话结论列：
- ai_takeaway（Text，可空）：谁受影响/偏利好利空/原因的一句中文结论。

与 b8e4d7f2a9c1 一致采用防御式幂等写法（列已存在则跳过）。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4f8a1d3e6b2'
down_revision: str | Sequence[str] | None = 'b8e4d7f2a9c1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema (defensive / idempotent)."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if 'news_item' not in inspector.get_table_names():
        return
    existing = {column['name'] for column in inspector.get_columns('news_item')}
    if 'ai_takeaway' not in existing:
        with op.batch_alter_table('news_item', schema=None) as batch_op:
            batch_op.add_column(sa.Column('ai_takeaway', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('news_item', schema=None) as batch_op:
        batch_op.drop_column('ai_takeaway')
