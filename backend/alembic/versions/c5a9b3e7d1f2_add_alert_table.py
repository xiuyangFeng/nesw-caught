"""add alert table (focus redesign P2)

站内提醒表，取代绑定飞书的 notification_job。``create_table`` 前先判断表是否已存在：
legacy 库修复路径会先按当前 metadata ``create_all`` 再 ``alembic upgrade``。

Revision ID: c5a9b3e7d1f2
Revises: c4e1d7a9b2f8
Create Date: 2026-11-01 08:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c5a9b3e7d1f2"
down_revision: str | Sequence[str] | None = "c4e1d7a9b2f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "alert"


def upgrade() -> None:
    if _TABLE_NAME in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        _TABLE_NAME,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("overnight", sa.Boolean(), nullable=False),
        sa.Column("visible_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index("ix_alert_kind", _TABLE_NAME, ["kind"], unique=False)
    op.create_index("ix_alert_symbol", _TABLE_NAME, ["symbol"], unique=False)
    op.create_index("ix_alert_visible_at", _TABLE_NAME, ["visible_at"], unique=False)


def downgrade() -> None:
    if _TABLE_NAME in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(_TABLE_NAME)
