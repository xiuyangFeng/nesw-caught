"""add_sentiment_eval_run

Revision ID: e6c2a9f4d1b7
Revises: d4b7e1f0c3a6
Create Date: 2026-08-02 12:00:00.000000

情绪评测模块重构 Phase 1（docs/superpowers/specs/2026-08-02-sentiment-eval-revamp-design.md）
工作块 B：POST /eval/sentiment/run 落库用的新表，一次 batch 下的多个模型 run
（rule-baseline / llm:* / hybrid:* / legacy 的 rule-sensitive）各存一行。

与 a7f3c1e9d2b4 / d4b7e1f0c3a6 保持同样的防御式写法：`create_table` 前先判断
表是否已存在——`db/initializer.py` 的 legacy 库修复路径会先按当前 metadata
`create_all`（新表已随 ORM 模型建好）再 `alembic upgrade`，非幂等写法会在该
路径报 "table already exists"。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e6c2a9f4d1b7'
down_revision: str | Sequence[str] | None = 'd4b7e1f0c3a6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = 'sentiment_eval_run'


def upgrade() -> None:
    """Upgrade schema (idempotent, tolerates create_all having already made this table)."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if _TABLE_NAME in inspector.get_table_names():
        return

    op.create_table(
        _TABLE_NAME,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dataset_path', sa.String(length=512), nullable=False),
        sa.Column('dataset_hash', sa.String(length=16), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(length=128), nullable=False),
        sa.Column('config_json', sa.Text(), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=False),
        sa.Column('macro_f1', sa.Float(), nullable=False),
        sa.Column('importance_weighted_accuracy', sa.Float(), nullable=True),
        sa.Column('per_label_json', sa.Text(), nullable=False),
        sa.Column('confusion_json', sa.Text(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_sentiment_eval_run_batch_id', _TABLE_NAME, ['batch_id'], unique=False
    )
    op.create_index(
        'ix_sentiment_eval_run_created_at', _TABLE_NAME, ['created_at'], unique=False
    )
    op.create_index(
        'ix_sentiment_eval_run_dataset_hash', _TABLE_NAME, ['dataset_hash'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_sentiment_eval_run_dataset_hash', table_name=_TABLE_NAME)
    op.drop_index('ix_sentiment_eval_run_created_at', table_name=_TABLE_NAME)
    op.drop_index('ix_sentiment_eval_run_batch_id', table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
