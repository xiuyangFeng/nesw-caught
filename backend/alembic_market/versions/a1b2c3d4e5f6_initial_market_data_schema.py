"""initial market_data schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-08-18 20:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())

    if "daily_bar" not in existing:
        op.create_table(
            "daily_bar",
            sa.Column("symbol", sa.String(length=16), nullable=False),
            sa.Column("trade_date", sa.Date(), nullable=False),
            sa.Column("open", sa.Float(), nullable=False),
            sa.Column("high", sa.Float(), nullable=False),
            sa.Column("low", sa.Float(), nullable=False),
            sa.Column("close", sa.Float(), nullable=False),
            sa.Column("volume", sa.Float(), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("turnover_rate", sa.Float(), nullable=True),
            sa.PrimaryKeyConstraint("symbol", "trade_date"),
        )
    if "index_daily_bar" not in existing:
        op.create_table(
            "index_daily_bar",
            sa.Column("index_code", sa.String(length=16), nullable=False),
            sa.Column("trade_date", sa.Date(), nullable=False),
            sa.Column("open", sa.Float(), nullable=False),
            sa.Column("high", sa.Float(), nullable=False),
            sa.Column("low", sa.Float(), nullable=False),
            sa.Column("close", sa.Float(), nullable=False),
            sa.Column("volume", sa.Float(), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.PrimaryKeyConstraint("index_code", "trade_date"),
        )
    if "trade_calendar" not in existing:
        op.create_table(
            "trade_calendar",
            sa.Column("trade_date", sa.Date(), nullable=False),
            sa.Column("is_open", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("trade_date"),
        )
    if "fund_flow_daily" not in existing:
        op.create_table(
            "fund_flow_daily",
            sa.Column("symbol", sa.String(length=16), nullable=False),
            sa.Column("trade_date", sa.Date(), nullable=False),
            sa.Column("main_net_inflow", sa.Float(), nullable=True),
            sa.Column("super_large_net", sa.Float(), nullable=True),
            sa.Column("large_net", sa.Float(), nullable=True),
            sa.Column("medium_net", sa.Float(), nullable=True),
            sa.Column("small_net", sa.Float(), nullable=True),
            sa.Column("main_net_pct", sa.Float(), nullable=True),
            sa.PrimaryKeyConstraint("symbol", "trade_date"),
        )


def downgrade() -> None:
    op.drop_table("fund_flow_daily")
    op.drop_table("trade_calendar")
    op.drop_table("index_daily_bar")
    op.drop_table("daily_bar")
