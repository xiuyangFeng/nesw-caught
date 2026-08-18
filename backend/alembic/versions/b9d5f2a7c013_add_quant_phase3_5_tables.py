"""add quant phase3-5 portfolio strategy paper tables

Revision ID: b9d5f2a7c013
Revises: a8c4e1f6b902
Create Date: 2026-08-18 22:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9d5f2a7c013"
down_revision: str | Sequence[str] | None = "a8c4e1f6b902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    tables = {
        "portfolio_proposal": lambda: op.create_table(
            "portfolio_proposal",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=True),
            sa.Column("cash_weight", sa.Float(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ),
        "portfolio_proposal_item": lambda: op.create_table(
            "portfolio_proposal_item",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("proposal_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("sleeve", sa.String(length=32), nullable=False),
            sa.Column("weight", sa.Float(), nullable=False),
            sa.Column("reject_reason", sa.String(length=64), nullable=True),
            sa.ForeignKeyConstraint(["proposal_id"], ["portfolio_proposal.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        ),
        "quant_strategy": lambda: op.create_table(
            "quant_strategy",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("dsl", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Integer(), nullable=False),
            sa.Column("exploratory", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ),
        "quant_backtest_run": lambda: op.create_table(
            "quant_backtest_run",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("strategy_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("exploratory", sa.Integer(), nullable=False),
            sa.Column("metrics", sa.Text(), nullable=False),
            sa.Column("note", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ),
        "paper_account": lambda: op.create_table(
            "paper_account",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("cash", sa.Float(), nullable=False),
            sa.Column("initial_cash", sa.Float(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ),
        "paper_order": lambda: op.create_table(
            "paper_order",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("side", sa.String(length=8), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("reject_reason", sa.String(length=64), nullable=True),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ),
        "paper_trade": lambda: op.create_table(
            "paper_trade",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("price", sa.Float(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ),
        "decision_log": lambda: op.create_table(
            "decision_log",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=True),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        ),
    }
    for name, create in tables.items():
        if name not in existing:
            create()


def downgrade() -> None:
    for name in (
        "decision_log",
        "paper_trade",
        "paper_order",
        "paper_account",
        "quant_backtest_run",
        "quant_strategy",
        "portfolio_proposal_item",
        "portfolio_proposal",
    ):
        op.drop_table(name)
