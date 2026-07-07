"""add_sqlite_fts5_fulltext_search

Revision ID: ec84dec88ae5
Revises: 6ca1c6bd4ed1
Create Date: 2026-06-13 12:24:40.493875

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec84dec88ae5'
down_revision: Union[str, Sequence[str], None] = '6ca1c6bd4ed1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 创建 FTS 虚表
    op.execute(
        "CREATE VIRTUAL TABLE news_fts USING fts5(title, summary, content='news_item', content_rowid='id')"
    )
    
    # 2. 回填存量数据
    op.execute(
        "INSERT INTO news_fts(rowid, title, summary) SELECT id, title, summary FROM news_item"
    )
    
    # 3. 创建触发器以同步写入、删除和更新
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


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS news_fts_ai")
    op.execute("DROP TRIGGER IF EXISTS news_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS news_fts_au")
    op.execute("DROP TABLE IF EXISTS news_fts")
