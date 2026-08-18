"""add quant phase2 research radar ai tables

Revision ID: a8c4e1f6b902
Revises: f7a1b8c2d4e0
Create Date: 2026-08-18 21:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8c4e1f6b902"
down_revision: str | Sequence[str] | None = "f7a1b8c2d4e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    if "radar_event" not in existing:
        op.create_table(
            "radar_event",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("news_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("evidence_grade", sa.String(length=8), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False),
            sa.Column("reason_code", sa.String(length=64), nullable=False),
            sa.Column("novelty", sa.Float(), nullable=False),
            sa.Column("materiality", sa.Float(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "research_snapshot" not in existing:
        op.create_table(
            "research_snapshot",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("display_name", sa.String(length=64), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("evidence_hash", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "llm_role_binding" not in existing:
        op.create_table(
            "llm_role_binding",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("tier", sa.String(length=16), nullable=False),
            sa.Column("config_id", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("role"),
        )
    if "ai_call_audit" not in existing:
        op.create_table(
            "ai_call_audit",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("prompt_version", sa.String(length=32), nullable=False),
            sa.Column("cache_hit", sa.Integer(), nullable=False),
            sa.Column("latency_ms", sa.Float(), nullable=False),
            sa.Column("token_in", sa.Integer(), nullable=False),
            sa.Column("token_out", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("pool", sa.String(length=32), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    op.drop_table("ai_call_audit")
    op.drop_table("llm_role_binding")
    op.drop_table("research_snapshot")
    op.drop_table("radar_event")
