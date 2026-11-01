"""drop sentiment_eval_run (focus redesign P1)

情绪评测工具下线：删除 e6c2a9f4d1b7 建出的 ``sentiment_eval_run`` 表。
downgrade 复用 e6c2a9f4d1b7 的 upgrade()（按"表不存在才建"实现），结构与下线前一致。

Revision ID: c3b8f0e2a5d6
Revises: c2a7e9d1f3b4
Create Date: 2026-11-01 04:00:00.000000
"""
from collections.abc import Sequence
from importlib import util as importlib_util
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision: str = "c3b8f0e2a5d6"
down_revision: str | Sequence[str] | None = "c2a7e9d1f3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "sentiment_eval_run"
_CREATING_MIGRATION = "e6c2a9f4d1b7_add_sentiment_eval_run.py"


def upgrade() -> None:
    if _TABLE_NAME in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(_TABLE_NAME)


def downgrade() -> None:
    path = Path(__file__).resolve().parent / _CREATING_MIGRATION
    spec = importlib_util.spec_from_file_location("_sentiment_eval_run_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
