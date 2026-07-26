"""perf_read_path_composite_indexes

Revision ID: d4b7e1f0c3a6
Revises: 0a513ac0e869
Create Date: 2026-07-25 22:10:00.000000

2026-07-25 后端/爬虫重构：补齐读路径缺失的复合索引。侦察发现以下查询此前
全部要走全表扫描或临时 b-tree 排序：

- news_item.sentiment_label **完全没有索引**，带情绪筛选的列表请求全表扫 + 排序；
- news_item.source_name 只有单列索引，无法同时服务 `ORDER BY effective_at DESC, id DESC`，
  按来源筛选时必然产生 temp sort；
- /news/runtime 的 `GROUP BY (source_name, market) + MAX(fetched_at)` 无对应索引；
- topic_news_link / news_stock_mention 只有单列索引，命中过滤列后仍需逐行回表
  取 join 键（feed-layout、portfolio、related-news 全都走这两条路径）；
- topic_cluster 每个 feed-layout / topics / 事件详情请求都按
  (importance_score, last_seen_at) 全量排序。

与 c6e9a2b4d8f1 / b5d8f1a3c7e2 一致：纯索引增删直接执行 CREATE/DROP INDEX
（不做 batch_alter_table 整表重建），并用 IF NOT EXISTS / IF EXISTS 保持幂等——
initialize_database 的 legacy 库修复路径会先按当前 metadata create_all
（索引已存在）再 alembic upgrade，非幂等写法会在该路径报 "already exists"。
"""
from collections.abc import Sequence

from sqlalchemy import inspect, text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4b7e1f0c3a6'
down_revision: str | Sequence[str] | None = '0a513ac0e869'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_news_sentiment_effective_id", "news_item", "sentiment_label, effective_at, id"),
    ("ix_news_source_effective_id", "news_item", "source_name, effective_at, id"),
    ("ix_news_source_market_fetched", "news_item", "source_name, market, fetched_at"),
    ("ix_topic_news_link_topic_news", "topic_news_link", "topic_cluster_id, news_id"),
    ("ix_news_stock_mention_symbol_news", "news_stock_mention", "symbol, news_id"),
    ("ix_topic_cluster_importance_seen", "topic_cluster", "importance_score, last_seen_at"),
)


def _existing_tables() -> set[str]:
    """本迁移可能运行在只含部分表的 legacy 库上。

    `CREATE INDEX IF NOT EXISTS` 只挡"索引已存在"，挡不住"表不存在"——
    后者仍会抛 OperationalError: no such table。历史迁移测试会构造只含
    notification_job 一张表的旧库再 upgrade 到 head（见
    tests/test_notification_dedupe.py），因此这里必须按表存在性逐条跳过。
    """
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """Upgrade schema (idempotent, tolerates partially-populated legacy DBs)."""
    tables = _existing_tables()
    for index_name, table_name, columns in _INDEXES:
        if table_name not in tables:
            continue
        op.execute(text(f'CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})'))


def downgrade() -> None:
    """Downgrade schema (idempotent)."""
    for index_name, _table_name, _columns in reversed(_INDEXES):
        op.execute(text(f'DROP INDEX IF EXISTS {index_name}'))
