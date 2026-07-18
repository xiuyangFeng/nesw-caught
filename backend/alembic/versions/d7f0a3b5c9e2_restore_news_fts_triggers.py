"""restore_news_fts_triggers

Revision ID: d7f0a3b5c9e2
Revises: c6e9a2b4d8f1
Create Date: 2026-07-18 17:00:00.000000

修复存量 bug：c4f8a1d3e6b2（batch_alter_table 加 ai_takeaway 列）在 SQLite 上
整表重建 news_item，连带丢弃 ec84dec88ae5 建立的三个 FTS 同步触发器，
此后 news_fts 停止增量同步（搜索静默退化为 LIKE 全表扫）。

本迁移：
1. 幂等重建 FTS 虚表（不存在才建）；
2. DROP + CREATE 三个同步触发器（DROP 兜底旧定义残留，保证定义确定性）；
3. VALUES('rebuild') 全量重建 FTS 内容，消除触发器缺失期间积累的漂移。
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd7f0a3b5c9e2'
down_revision: str | Sequence[str] | None = 'c6e9a2b4d8f1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS news_fts USING fts5(title, summary, content='news_item', content_rowid='id')"
    )

    op.execute("DROP TRIGGER IF EXISTS news_fts_ai")
    op.execute("DROP TRIGGER IF EXISTS news_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS news_fts_au")

    op.execute("""
    CREATE TRIGGER news_fts_ai AFTER INSERT ON news_item BEGIN
        INSERT INTO news_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
    END;
    """)

    op.execute("""
    CREATE TRIGGER news_fts_ad AFTER DELETE ON news_item BEGIN
        INSERT INTO news_fts(news_fts, rowid, title, summary) VALUES('delete', old.id, old.title, old.summary);
    END;
    """)

    op.execute("""
    CREATE TRIGGER news_fts_au AFTER UPDATE OF title, summary ON news_item BEGIN
        INSERT INTO news_fts(news_fts, rowid, title, summary) VALUES('delete', old.id, old.title, old.summary);
        INSERT INTO news_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
    END;
    """)

    # 全量重建 FTS 内容（external-content 表的内建命令），清除触发器缺失期的漂移
    op.execute("INSERT INTO news_fts(news_fts) VALUES('rebuild')")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS news_fts_ai")
    op.execute("DROP TRIGGER IF EXISTS news_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS news_fts_au")
