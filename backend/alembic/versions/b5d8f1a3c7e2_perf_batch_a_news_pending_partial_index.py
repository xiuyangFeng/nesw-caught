"""perf_batch_a_news_pending_partial_index

Revision ID: b5d8f1a3c7e2
Revises: f3a7c1e9b5d2
Create Date: 2026-07-18 07:30:00.000000

性能优化批次 A：
- 新增 partial index ix_news_pending ON news_item(id) WHERE signal_status IS NULL，
  支撑信号流水线 list_pending_news_ids 的 pending 队列查询（只索引待处理行）。
- 删除写放大冗余单列索引：ix_news_item_title；以及与复合索引前缀重复的
  ix_news_item_published_at（前缀 ix_news_published_id）和
  ix_news_item_market（前缀 ix_news_market_published_id / ix_news_market_effective_id）。

纯索引增删使用 op.create_index / op.drop_index 直接执行（SQLite 原生
CREATE/DROP INDEX），而非 batch_alter_table 整表重建：news_item 是库内最大表，
重建拷贝代价高，且 DROP TABLE 会连带删除 ec84dec88ae5 创建的 FTS 同步触发器。
"""
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b5d8f1a3c7e2'
down_revision: str | Sequence[str] | None = 'f3a7c1e9b5d2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    使用 IF NOT EXISTS / IF EXISTS 保持幂等:initialize_database 的 legacy 库
    修复路径会先按当前 metadata create_all(索引已存在)再 alembic upgrade,
    非幂等的 CREATE/DROP INDEX 会在该路径上报 "already exists/no such index"。
    """
    op.execute(
        text('CREATE INDEX IF NOT EXISTS ix_news_pending ON news_item (id) WHERE signal_status IS NULL')
    )
    op.execute(text('DROP INDEX IF EXISTS ix_news_item_title'))
    op.execute(text('DROP INDEX IF EXISTS ix_news_item_published_at'))
    op.execute(text('DROP INDEX IF EXISTS ix_news_item_market'))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(text('CREATE INDEX IF NOT EXISTS ix_news_item_market ON news_item (market)'))
    op.execute(text('CREATE INDEX IF NOT EXISTS ix_news_item_published_at ON news_item (published_at)'))
    op.execute(text('CREATE INDEX IF NOT EXISTS ix_news_item_title ON news_item (title)'))
    op.execute(text('DROP INDEX IF EXISTS ix_news_pending'))
