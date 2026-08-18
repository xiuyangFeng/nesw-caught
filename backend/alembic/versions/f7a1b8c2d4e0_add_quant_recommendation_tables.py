"""add_quant_recommendation_tables

Revision ID: f7a1b8c2d4e0
Revises: e6c2a9f4d1b7
Create Date: 2026-08-18 19:30:00.000000

量化交易台 Phase 0：主库业务状态表 recommendation_run / recommendation_item /
quant_run_stage_log。独立行情库 market_data.db 留给 Phase 1。

与既有迁移一样做幂等：initializer 的 fresh/legacy 路径会先 create_all，
非幂等 create_table 会在 upgrade 时报 table already exists。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f7a1b8c2d4e0"
down_revision: str | Sequence[str] | None = "e6c2a9f4d1b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())

    if "recommendation_run" not in existing:
        op.create_table(
            "recommendation_run",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("run_date", sa.Date(), nullable=False),
            sa.Column("source_cutoff", sa.DateTime(timezone=True), nullable=False),
            sa.Column("trigger", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("scenario", sa.String(length=32), nullable=False),
            sa.Column("dataset_version", sa.String(length=64), nullable=False),
            sa.Column("factor_version", sa.String(length=64), nullable=False),
            sa.Column("rule_version", sa.String(length=64), nullable=False),
            sa.Column("code_commit", sa.String(length=64), nullable=False),
            sa.Column("config_snapshot", sa.Text(), nullable=False),
            sa.Column("result_hash", sa.String(length=64), nullable=False),
            sa.Column("empty_reason", sa.String(length=64), nullable=True),
            sa.Column("empty_reason_detail", sa.Text(), nullable=True),
            sa.Column("llm_config_id", sa.Integer(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_recommendation_run_run_date", "recommendation_run", ["run_date"])
        op.create_index("ix_recommendation_run_status", "recommendation_run", ["status"])
        op.create_index("ix_recommendation_run_result_hash", "recommendation_run", ["result_hash"])

    if "recommendation_item" not in existing:
        op.create_table(
            "recommendation_item",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("display_name", sa.String(length=64), nullable=False),
            sa.Column("sleeve", sa.String(length=32), nullable=False),
            sa.Column("horizon", sa.String(length=16), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False),
            sa.Column("rank", sa.Integer(), nullable=True),
            sa.Column("deterministic_score", sa.Float(), nullable=False),
            sa.Column("reason_code", sa.String(length=64), nullable=False),
            sa.Column("factor_breakdown", sa.Text(), nullable=False),
            sa.Column("thesis_md", sa.Text(), nullable=True),
            sa.Column("anti_thesis_md", sa.Text(), nullable=True),
            sa.Column("invalidation_condition", sa.Text(), nullable=True),
            sa.Column("valid_until", sa.Date(), nullable=True),
            sa.Column("evidence_ids", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["recommendation_run.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_recommendation_item_run_id", "recommendation_item", ["run_id"])
        op.create_index("ix_recommendation_item_symbol", "recommendation_item", ["symbol"])
        op.create_index("ix_recommendation_item_sleeve", "recommendation_item", ["sleeve"])
        op.create_index("ix_recommendation_item_state", "recommendation_item", ["state"])

    if "quant_run_stage_log" not in existing:
        op.create_table(
            "quant_run_stage_log",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=False),
            sa.Column("stage", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["recommendation_run.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_quant_run_stage_log_run_id", "quant_run_stage_log", ["run_id"])
        op.create_index("ix_quant_run_stage_log_stage", "quant_run_stage_log", ["stage"])


def downgrade() -> None:
    op.drop_index("ix_quant_run_stage_log_stage", table_name="quant_run_stage_log")
    op.drop_index("ix_quant_run_stage_log_run_id", table_name="quant_run_stage_log")
    op.drop_table("quant_run_stage_log")
    op.drop_index("ix_recommendation_item_state", table_name="recommendation_item")
    op.drop_index("ix_recommendation_item_sleeve", table_name="recommendation_item")
    op.drop_index("ix_recommendation_item_symbol", table_name="recommendation_item")
    op.drop_index("ix_recommendation_item_run_id", table_name="recommendation_item")
    op.drop_table("recommendation_item")
    op.drop_index("ix_recommendation_run_result_hash", table_name="recommendation_run")
    op.drop_index("ix_recommendation_run_status", table_name="recommendation_run")
    op.drop_index("ix_recommendation_run_run_date", table_name="recommendation_run")
    op.drop_table("recommendation_run")
