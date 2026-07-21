"""notification_job_dedupe_key_unique_index

Revision ID: 0a513ac0e869
Revises: d7f0a3b5c9e2
Create Date: 2026-07-21 09:00:00.000000

背景：notification_job 幂等入队目前靠 repository 层"先查后插"（先 SELECT
dedupe_key 命中即返回，未命中才 INSERT），dedupe_key 只有普通索引，并发
入队时两个请求可能都查不到而各自插入一行，产生重复通知。

本迁移：
1. 清理历史重复：同一非空 dedupe_key 若有多行，只保留 id 最大的一条，
   其余行的 dedupe_key 置为 NULL（不删行，保留审计轨迹）。
2. 对非空 dedupe_key 建部分唯一索引（SQLite partial unique index，只约束
   dedupe_key IS NOT NULL 的行），把去重从"应用层先查后插"升级为数据库
   约束兜底；dedupe_key 为 NULL 的弱去重行不受影响。
3. 删除旧的普通单列索引 ix_notification_job_dedupe_key——新的唯一索引已
   覆盖等值查询场景（get_by_dedupe_key 只按具体非空 key 查询），继续保留
   两份索引只会增加写放大。

纯索引增删 + 数据修复使用 op.execute 直接执行幂等 raw SQL（IF NOT
EXISTS / IF EXISTS），而非 batch_alter_table 整表重建：notification_job
上的 batch 重建曾在 c4f8a1d3e6b2 类似场景下连带丢过 news_item 的 FTS
同步触发器（见 d7f0a3b5c9e2 的修复记录），本迁移不表所在但同样规避该
写法以保持一致的迁移风格。
"""
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0a513ac0e869'
down_revision: str | Sequence[str] | None = 'd7f0a3b5c9e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    幂等设计：UPDATE 清理在没有重复行时是空操作；CREATE/DROP INDEX 均带
    IF NOT EXISTS / IF EXISTS，重复执行（如 initialize_database 的 legacy
    库修复路径）不会报错。
    """
    # 1) 历史重复 dedupe_key：每组只留 id 最大的一条，其余置 NULL。
    op.execute(
        text(
            """
            UPDATE notification_job
            SET dedupe_key = NULL
            WHERE dedupe_key IS NOT NULL
              AND id NOT IN (
                  SELECT MAX(id) FROM notification_job
                  WHERE dedupe_key IS NOT NULL
                  GROUP BY dedupe_key
              )
            """
        )
    )

    # 2) 非空 dedupe_key 唯一约束（partial unique index）。
    op.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_notification_job_dedupe_key "
            "ON notification_job (dedupe_key) WHERE dedupe_key IS NOT NULL"
        )
    )

    # 3) 旧的普通单列索引被新唯一索引取代，删除避免写放大。
    op.execute(text('DROP INDEX IF EXISTS ix_notification_job_dedupe_key'))


def downgrade() -> None:
    """Downgrade schema.

    只回滚索引结构，不恢复被置 NULL 的历史 dedupe_key 值——该数据修复是
    单向的（同 b5d8f1a3c7e2 的索引增删风格），原始重复值已不可逆地丢失。
    """
    op.execute(
        text('CREATE INDEX IF NOT EXISTS ix_notification_job_dedupe_key ON notification_job (dedupe_key)')
    )
    op.execute(text('DROP INDEX IF EXISTS ux_notification_job_dedupe_key'))
