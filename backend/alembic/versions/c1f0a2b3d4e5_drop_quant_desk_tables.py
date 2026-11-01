"""drop quant desk tables (focus redesign P1)

量化交易台整体下线：删除 f7a1b8c2d4e0 / a8c4e1f6b902 / b9d5f2a7c013 三个迁移建出的 15 张表。
downgrade 直接复用这三个迁移的 upgrade()（它们本身按"表不存在才建"实现，可重复执行），
保证回退后的表结构与下线前完全一致。

Revision ID: c1f0a2b3d4e5
Revises: b9d5f2a7c013
Create Date: 2026-11-01 02:00:00.000000
"""
from collections.abc import Sequence
from importlib import util as importlib_util
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision: str = "c1f0a2b3d4e5"
down_revision: str | Sequence[str] | None = "b9d5f2a7c013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 按依赖逆序删除（子表在前）。
QUANT_TABLES: tuple[str, ...] = (
    "decision_log",
    "paper_trade",
    "paper_order",
    "paper_account",
    "quant_backtest_run",
    "quant_strategy",
    "portfolio_proposal_item",
    "portfolio_proposal",
    "ai_call_audit",
    "llm_role_binding",
    "research_snapshot",
    "radar_event",
    "quant_run_stage_log",
    "recommendation_item",
    "recommendation_run",
)

_CREATING_MIGRATIONS: tuple[str, ...] = (
    "f7a1b8c2d4e0_add_quant_recommendation_tables.py",
    "a8c4e1f6b902_add_quant_phase2_research_radar_ai_tables.py",
    "b9d5f2a7c013_add_quant_phase3_5_tables.py",
)


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for name in QUANT_TABLES:
        if name in existing:
            op.drop_table(name)


def downgrade() -> None:
    versions_dir = Path(__file__).resolve().parent
    for filename in _CREATING_MIGRATIONS:
        spec = importlib_util.spec_from_file_location(f"_quant_migration_{filename[:12]}", versions_dir / filename)
        assert spec is not None and spec.loader is not None
        module = importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.upgrade()
