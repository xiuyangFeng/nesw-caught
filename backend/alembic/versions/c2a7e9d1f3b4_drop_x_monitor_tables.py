"""drop x monitor tables (focus redesign P1)

X 监控整体下线（用户选择依赖华尔街见闻 / 财联社等已接入快讯源）。删除 6 张 ``x_*`` 表。
这些表大多由早期 ``create_all`` 建出、迁移链中没有建表记录，因此 downgrade 直接回放
下线前从真实库 ``sqlite_master`` 取得的原始 DDL（本项目只使用 SQLite），结构与下线前一致。

Revision ID: c2a7e9d1f3b4
Revises: c1f0a2b3d4e5
Create Date: 2026-11-01 03:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c2a7e9d1f3b4"
down_revision: str | Sequence[str] | None = "c1f0a2b3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 按外键依赖逆序删除（子表在前）。
X_TABLES: tuple[str, ...] = (
    "x_signal_post_link",
    "x_post_symbol_mention",
    "x_signal",
    "x_post",
    "x_source_health",
    "x_account",
)

# 下线前 app.db 中的原始 DDL（父表在前）。
_RESTORE_DDL: tuple[str, ...] = (
    'CREATE TABLE "x_account" (\n\tid INTEGER NOT NULL, \n\thandle VARCHAR(64) NOT NULL, \n\tdisplay_name VARCHAR(128) NOT NULL, \n\tmarket_focus VARCHAR(16), \n\tis_active BOOLEAN NOT NULL, \n\tpriority INTEGER NOT NULL, \n\tnotes TEXT, \n\ttier VARCHAR(16) DEFAULT \'watch\' NOT NULL, \n\tsource VARCHAR(32) DEFAULT \'manual\' NOT NULL, \n\tPRIMARY KEY (id)\n)',
    'CREATE UNIQUE INDEX ix_x_account_handle ON x_account (handle)',
    'CREATE TABLE x_source_health (\n\tid INTEGER NOT NULL, \n\tprovider_name VARCHAR(64) NOT NULL, \n\tlast_success_at DATETIME, \n\tlast_failure_at DATETIME, \n\tconsecutive_failures INTEGER NOT NULL, \n\ttotal_fetches INTEGER NOT NULL, \n\ttotal_failures INTEGER NOT NULL, \n\tavg_latency_ms FLOAT, \n\tlast_error TEXT, \n\tPRIMARY KEY (id)\n)',
    'CREATE UNIQUE INDEX ix_x_source_health_provider_name ON x_source_health (provider_name)',
    'CREATE TABLE x_post (\n\tid INTEGER NOT NULL, \n\taccount_id INTEGER NOT NULL, \n\texternal_post_id VARCHAR(64), \n\tcanonical_url VARCHAR(500), \n\tcontent_text TEXT NOT NULL, \n\tmarket VARCHAR(16) NOT NULL, \n\tsentiment_label VARCHAR(16) NOT NULL, \n\trelevance_score FLOAT, \n\tposted_at DATETIME, \n\tcaptured_at DATETIME NOT NULL, \n\traw_payload_json TEXT, \n\tdedupe_hash VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(account_id) REFERENCES x_account (id), \n\tUNIQUE (external_post_id), \n\tUNIQUE (canonical_url)\n)',
    'CREATE INDEX ix_x_post_account_id ON x_post (account_id)',
    'CREATE INDEX ix_x_post_captured_at ON x_post (captured_at)',
    'CREATE UNIQUE INDEX ix_x_post_dedupe_hash ON x_post (dedupe_hash)',
    'CREATE INDEX ix_x_post_market ON x_post (market)',
    'CREATE INDEX ix_x_post_posted_at ON x_post (posted_at)',
    'CREATE TABLE x_post_symbol_mention (\n\tid INTEGER NOT NULL, \n\tx_post_id INTEGER NOT NULL, \n\tsymbol VARCHAR(32) NOT NULL, \n\tmarket VARCHAR(16) NOT NULL, \n\tconfidence FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(x_post_id) REFERENCES x_post (id)\n)',
    'CREATE INDEX ix_x_post_symbol_mention_market ON x_post_symbol_mention (market)',
    'CREATE INDEX ix_x_post_symbol_mention_symbol ON x_post_symbol_mention (symbol)',
    'CREATE INDEX ix_x_post_symbol_mention_x_post_id ON x_post_symbol_mention (x_post_id)',
    'CREATE TABLE x_signal (\n\tid INTEGER NOT NULL, \n\tsignal_type VARCHAR(32) NOT NULL, \n\ttitle VARCHAR(255) NOT NULL, \n\tsummary TEXT NOT NULL, \n\tmarket VARCHAR(16) NOT NULL, \n\ttopic_tag VARCHAR(64), \n\tmacro_tag VARCHAR(64), \n\tprimary_symbol VARCHAR(32), \n\tpriority_score FLOAT NOT NULL, \n\tconfidence_score FLOAT NOT NULL, \n\tsource_count INTEGER NOT NULL, \n\tfirst_seen_at DATETIME NOT NULL, \n\tlast_seen_at DATETIME NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tPRIMARY KEY (id)\n)',
    'CREATE INDEX ix_x_signal_first_seen_at ON x_signal (first_seen_at)',
    'CREATE INDEX ix_x_signal_last_seen_at ON x_signal (last_seen_at)',
    'CREATE INDEX ix_x_signal_macro_tag ON x_signal (macro_tag)',
    'CREATE INDEX ix_x_signal_market ON x_signal (market)',
    'CREATE INDEX ix_x_signal_primary_symbol ON x_signal (primary_symbol)',
    'CREATE INDEX ix_x_signal_priority_score ON x_signal (priority_score)',
    'CREATE INDEX ix_x_signal_signal_type ON x_signal (signal_type)',
    'CREATE INDEX ix_x_signal_status ON x_signal (status)',
    'CREATE INDEX ix_x_signal_topic_tag ON x_signal (topic_tag)',
    'CREATE TABLE x_signal_post_link (\n\tid INTEGER NOT NULL, \n\tsignal_id INTEGER NOT NULL, \n\tpost_id INTEGER NOT NULL, \n\tevidence_rank INTEGER NOT NULL, \n\tmatch_reason VARCHAR(64), \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_x_signal_post_link_signal_post UNIQUE (signal_id, post_id), \n\tFOREIGN KEY(signal_id) REFERENCES x_signal (id), \n\tFOREIGN KEY(post_id) REFERENCES x_post (id)\n)',
    'CREATE INDEX ix_x_signal_post_link_post_id ON x_signal_post_link (post_id)',
    'CREATE INDEX ix_x_signal_post_link_signal_id ON x_signal_post_link (signal_id)',
)


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for name in X_TABLES:
        if name in existing:
            op.drop_table(name)


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if existing.intersection(X_TABLES):
        return
    for statement in _RESTORE_DDL:
        op.execute(statement)
