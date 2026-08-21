"""add financial_fact (eastmoney quarterly financials, PIT)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-21 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    if "financial_fact" not in existing:
        op.create_table(
            "financial_fact",
            sa.Column("symbol", sa.String(length=16), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("metric_key", sa.String(length=32), nullable=False),
            sa.Column("value", sa.Float(), nullable=True),
            sa.Column("available_at", sa.Date(), nullable=True),
            sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("document_id", sa.String(length=64), nullable=False, server_default=""),
            sa.PrimaryKeyConstraint("symbol", "period_end", "metric_key"),
        )
        op.create_index("ix_financial_fact_available_at", "financial_fact", ["available_at"])


def downgrade() -> None:
    op.drop_table("financial_fact")
