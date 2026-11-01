"""drop feishu notification tables and per-stock alert columns (focus redesign P2)

站内提醒（``alert`` 表）取代飞书推送：删除 ``feishu_notify_config``、``notification_job``；
用户确认价格提醒统一阈值、不按股票分别设置，删除 ``watchlist_item.alert_threshold`` /
``alert_mode``（删除前用户库中 alert_threshold 全部为空）。

downgrade 回放下线前从真实库取得的原始 DDL（本项目只用 SQLite），并把两列加回。

Revision ID: c6d2f8a4e9b1
Revises: c5a9b3e7d1f2
Create Date: 2026-11-01 09:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c6d2f8a4e9b1"
down_revision: str | Sequence[str] | None = "c5a9b3e7d1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROPPED_TABLES: tuple[str, ...] = ("notification_job", "feishu_notify_config")
_DROPPED_COLUMNS: tuple[str, ...] = ("alert_threshold", "alert_mode")

# 下线前 app.db 中的原始 DDL。
_RESTORE_DDL: tuple[str, ...] = (
    'CREATE TABLE feishu_notify_config (\n\tid INTEGER NOT NULL, \n\tapp_id VARCHAR(128) NOT NULL, \n\tapp_secret VARCHAR(256) NOT NULL, \n\ttarget_type VARCHAR(16) NOT NULL, \n\ttarget_id VARCHAR(128) NOT NULL, \n\tnews_enabled BOOLEAN NOT NULL, \n\tnews_keywords TEXT, \n\tnews_batch_interval_minutes INTEGER NOT NULL, \n\talert_enabled BOOLEAN NOT NULL, \n\tanalysis_enabled BOOLEAN NOT NULL, \n\tis_active BOOLEAN NOT NULL, \n\tupdated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id)\n)',
    'CREATE TABLE notification_job (\n\tid INTEGER NOT NULL, \n\tchannel VARCHAR(32) NOT NULL, \n\tevent_type VARCHAR(64) NOT NULL, \n\tpayload_json TEXT NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tattempt_count INTEGER NOT NULL, \n\tnext_retry_at DATETIME, \n\tdedupe_key VARCHAR(255), \n\tlast_error TEXT, \n\tlease_until DATETIME, \n\tsent_at DATETIME, \n\tcreated_at DATETIME NOT NULL, lease_token VARCHAR(64), \n\tPRIMARY KEY (id)\n)',
    'CREATE INDEX ix_notification_job_channel ON notification_job (channel)',
    'CREATE INDEX ix_notification_job_event_type ON notification_job (event_type)',
    'CREATE INDEX ix_notification_job_lease_token ON notification_job (lease_token)',
    'CREATE INDEX ix_notification_job_lease_until ON notification_job (lease_until)',
    'CREATE INDEX ix_notification_job_next_retry_at ON notification_job (next_retry_at)',
    'CREATE INDEX ix_notification_job_sent_at ON notification_job (sent_at)',
    'CREATE INDEX ix_notification_job_status ON notification_job (status)',
    'CREATE UNIQUE INDEX ux_notification_job_dedupe_key ON notification_job (dedupe_key) WHERE dedupe_key IS NOT NULL',
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    for name in _DROPPED_TABLES:
        if name in existing:
            op.drop_table(name)
    if "watchlist_item" in existing:
        columns = {column["name"] for column in inspector.get_columns("watchlist_item")}
        to_drop = [name for name in _DROPPED_COLUMNS if name in columns]
        if to_drop:
            with op.batch_alter_table("watchlist_item") as batch_op:
                for name in to_drop:
                    batch_op.drop_column(name)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    if not existing.intersection(_DROPPED_TABLES):
        for statement in _RESTORE_DDL:
            op.execute(statement)
    columns = {column["name"] for column in inspector.get_columns("watchlist_item")}
    with op.batch_alter_table("watchlist_item") as batch_op:
        if "alert_threshold" not in columns:
            batch_op.add_column(sa.Column("alert_threshold", sa.Float(), nullable=True))
        if "alert_mode" not in columns:
            batch_op.add_column(
                sa.Column("alert_mode", sa.String(length=16), nullable=False, server_default="fixed")
            )
