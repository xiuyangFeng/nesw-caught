"""source_health status and empty-batch fields

Revision ID: d1a2b3c4e5f6
Revises: c4f8a1d3e6b2
Create Date: 2026-07-17 19:30:00.000000

Adds fetch outcome diagnostics used by scheduler circuit-breaking:
last_status, last_error, last_http_status, last_fetched_count,
last_inserted_count, consecutive_empty_batches.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1a2b3c4e5f6"
down_revision: str | Sequence[str] | None = "c4f8a1d3e6b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS: list[tuple[str, sa.Column]] = [
    ("last_status", sa.Column("last_status", sa.String(length=32), nullable=True)),
    ("last_error", sa.Column("last_error", sa.Text(), nullable=True)),
    ("last_http_status", sa.Column("last_http_status", sa.Integer(), nullable=True)),
    ("last_fetched_count", sa.Column("last_fetched_count", sa.Integer(), nullable=False, server_default="0")),
    ("last_inserted_count", sa.Column("last_inserted_count", sa.Integer(), nullable=False, server_default="0")),
    ("consecutive_empty_batches", sa.Column("consecutive_empty_batches", sa.Integer(), nullable=False, server_default="0")),
]


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "source_health" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("source_health")}
    with op.batch_alter_table("source_health", schema=None) as batch_op:
        for name, column in _COLUMNS:
            if name not in existing:
                batch_op.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("source_health", schema=None) as batch_op:
        for name, _ in reversed(_COLUMNS):
            batch_op.drop_column(name)
