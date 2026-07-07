"""add_news_item_composite_indexes

Revision ID: 6ca1c6bd4ed1
Revises: b3e502be1b9f
Create Date: 2026-06-13 12:20:00.493875

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ca1c6bd4ed1'
down_revision: Union[str, Sequence[str], None] = 'b3e502be1b9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('news_item', schema=None) as batch_op:
        batch_op.create_index('ix_news_market_published_id', ['market', 'published_at', 'id'], unique=False)
        batch_op.create_index('ix_news_published_id', ['published_at', 'id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('news_item', schema=None) as batch_op:
        batch_op.drop_index('ix_news_published_id')
        batch_op.drop_index('ix_news_market_published_id')
