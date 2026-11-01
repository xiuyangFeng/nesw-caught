"""AI funnel tables; LLM unit prices per 1M tokens (focus redesign P3)

- ``llm_provider_config.input_price_per_1k`` / ``output_price_per_1k`` 改名为 ``*_per_1m``，
  数值不变。原"每 1K"口径下 DeepSeek 配置（0.02 / 1.0）折合每百万 $20 / $1000，明显误填；
  按每百万重新解读后为 $0.02 / $1.0。
- 新建 AI 漏斗表：``news_ai_screen``、``news_ai_analysis``、``news_impact``、
  ``impact_correction``、``stock_sector``、``focus_sector_override``。

Revision ID: c7e4a1b9d3f6
Revises: c6d2f8a4e9b1
Create Date: 2026-11-01 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7e4a1b9d3f6"
down_revision: str | Sequence[str] | None = "c6d2f8a4e9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRICE_RENAMES = (("input_price_per_1k", "input_price_per_1m"), ("output_price_per_1k", "output_price_per_1m"))


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _llm_columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("llm_provider_config")}


def _news_fk() -> sa.ForeignKey:
    return sa.ForeignKey("news_item.id", ondelete="CASCADE")


def upgrade() -> None:
    columns = _llm_columns()
    # legacy 引导路径（create_all 已建出 *_per_1m，之后 a7f3c1e9d2b4 又补了 *_per_1k）
    # 会两套列并存：先把旧列数值搬到新列，再删旧列。
    for old, new in _PRICE_RENAMES:
        if old in columns and new in columns:
            op.execute(f"UPDATE llm_provider_config SET {new} = {old} WHERE {new} IS NULL")
    with op.batch_alter_table("llm_provider_config") as batch_op:
        for old, new in _PRICE_RENAMES:
            if old in columns and new not in columns:
                batch_op.alter_column(old, new_column_name=new)
            elif old in columns and new in columns:
                batch_op.drop_column(old)

    tables = _existing_tables()
    if "news_ai_screen" not in tables:
        op.create_table(
            "news_ai_screen",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("news_id", sa.Integer(), _news_fk(), nullable=False),
            sa.Column("importance", sa.Integer(), nullable=False),
            sa.Column("overseas", sa.Boolean(), nullable=False),
            sa.Column("deep_read", sa.Boolean(), nullable=False),
            sa.Column("title_zh", sa.Text(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("model_name", sa.String(length=128), nullable=True),
            sa.Column("screened_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_news_ai_screen_news_id", "news_ai_screen", ["news_id"], unique=True)
        op.create_index("ix_news_ai_screen_deep_read", "news_ai_screen", ["deep_read"])
        op.create_index("ix_news_ai_screen_status", "news_ai_screen", ["status"])
        op.create_index("ix_news_ai_screen_screened_at", "news_ai_screen", ["screened_at"])

    if "news_ai_analysis" not in tables:
        op.create_table(
            "news_ai_analysis",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("news_id", sa.Integer(), _news_fk(), nullable=False),
            sa.Column("summary_zh", sa.Text(), nullable=True),
            sa.Column("view", sa.Text(), nullable=True),
            sa.Column("major", sa.Boolean(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("model_name", sa.String(length=128), nullable=True),
            sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_news_ai_analysis_news_id", "news_ai_analysis", ["news_id"], unique=True)
        op.create_index("ix_news_ai_analysis_status", "news_ai_analysis", ["status"])
        op.create_index("ix_news_ai_analysis_analyzed_at", "news_ai_analysis", ["analyzed_at"])

    if "news_impact" not in tables:
        op.create_table(
            "news_impact",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("news_id", sa.Integer(), _news_fk(), nullable=False),
            sa.Column("target_type", sa.String(length=16), nullable=False),
            sa.Column("target_code", sa.String(length=32), nullable=True),
            sa.Column("target_name", sa.String(length=128), nullable=False),
            sa.Column("direction", sa.String(length=16), nullable=False),
            sa.Column("strength", sa.String(length=16), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_news_impact_news_id", "news_impact", ["news_id"])
        op.create_index("ix_news_impact_target_code", "news_impact", ["target_code"])
        op.create_index("ix_news_impact_target_name", "news_impact", ["target_name"])
        op.create_index("ix_news_impact_created_at", "news_impact", ["created_at"])

    if "impact_correction" not in tables:
        op.create_table(
            "impact_correction",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("news_id", sa.Integer(), _news_fk(), nullable=False),
            sa.Column("news_title", sa.Text(), nullable=False),
            sa.Column("before_json", sa.Text(), nullable=False),
            sa.Column("after_json", sa.Text(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_impact_correction_news_id", "impact_correction", ["news_id"])
        op.create_index("ix_impact_correction_created_at", "impact_correction", ["created_at"])

    if "stock_sector" not in tables:
        op.create_table(
            "stock_sector",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("sector", sa.String(length=64), nullable=False),
            sa.Column("source", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("symbol", "sector", name="ux_stock_sector_symbol_sector"),
        )
        op.create_index("ix_stock_sector_symbol", "stock_sector", ["symbol"])

    if "focus_sector_override" not in tables:
        op.create_table(
            "focus_sector_override",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sector", sa.String(length=64), nullable=False, unique=True),
            sa.Column("action", sa.String(length=8), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    tables = _existing_tables()
    for table in (
        "focus_sector_override",
        "stock_sector",
        "impact_correction",
        "news_impact",
        "news_ai_analysis",
        "news_ai_screen",
    ):
        if table in tables:
            op.drop_table(table)

    columns = _llm_columns()
    with op.batch_alter_table("llm_provider_config") as batch_op:
        for old, new in _PRICE_RENAMES:
            if new in columns and old not in columns:
                batch_op.alter_column(new, new_column_name=old)
