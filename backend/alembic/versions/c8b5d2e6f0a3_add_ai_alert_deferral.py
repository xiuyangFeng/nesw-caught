"""add ai_alert_deferral (focus redesign P3 review fix)

AI 模式下被跳过的关键词命中先记下来；AI 15 分钟内没给出结论（漏斗报错、额度用完、
超预算、模型被取消等）就按关键词补发，保证持仓新闻不漏提醒。

Revision ID: c8b5d2e6f0a3
Revises: c7e4a1b9d3f6
Create Date: 2026-11-01 16:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8b5d2e6f0a3"
down_revision: str | Sequence[str] | None = "c7e4a1b9d3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "ai_alert_deferral" in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        "ai_alert_deferral",
        sa.Column("news_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=True),
        sa.Column("market", sa.String(length=16), nullable=True),
        sa.Column("deferred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_alert_deferral_deferred_at", "ai_alert_deferral", ["deferred_at"])


def downgrade() -> None:
    if "ai_alert_deferral" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("ai_alert_deferral")
