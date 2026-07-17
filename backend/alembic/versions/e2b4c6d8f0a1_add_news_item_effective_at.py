"""add news_item.effective_at and sort indexes

Revision ID: e2b4c6d8f0a1
Revises: d1a2b3c4e5f6
Create Date: 2026-07-17 19:45:00.000000

Adds effective_at = COALESCE(published_at, fetched_at) for list/cursor ordering,
plus composite indexes (effective_at, id) / (market, effective_at, id).

Defensive / idempotent: skips when column or indexes already exist.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "e2b4c6d8f0a1"
down_revision: str | Sequence[str] | None = "d1a2b3c4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES: list[tuple[str, list[str]]] = [
    ("ix_news_effective_id", ["effective_at", "id"]),
    ("ix_news_market_effective_id", ["market", "effective_at", "id"]),
]


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "news_item" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("news_item")}
    if "effective_at" not in existing_columns:
        with op.batch_alter_table("news_item", schema=None) as batch_op:
            batch_op.add_column(sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True))
        connection.execute(
            text(
                """
                UPDATE news_item
                SET effective_at = COALESCE(published_at, fetched_at)
                WHERE effective_at IS NULL
                """
            )
        )
        with op.batch_alter_table("news_item", schema=None) as batch_op:
            batch_op.alter_column("effective_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    inspector = sa.inspect(connection)
    existing_indexes = {index["name"] for index in inspector.get_indexes("news_item")}
    with op.batch_alter_table("news_item", schema=None) as batch_op:
        for name, columns in _INDEXES:
            if name not in existing_indexes:
                batch_op.create_index(name, columns, unique=False)


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "news_item" not in inspector.get_table_names():
        return

    existing_indexes = {index["name"] for index in inspector.get_indexes("news_item")}
    existing_columns = {column["name"] for column in inspector.get_columns("news_item")}
    with op.batch_alter_table("news_item", schema=None) as batch_op:
        for name, _columns in _INDEXES:
            if name in existing_indexes:
                batch_op.drop_index(name)
        if "effective_at" in existing_columns:
            batch_op.drop_column("effective_at")
