"""Alembic 迁移链与 ORM ``Base.metadata`` 的 schema 一致性测试。

背景（架构加固计划 Wave 3a Task 11）：``db/initializer.py`` 的三条初始化
路径里，全新库（fresh）和几乎所有测试都走 ``create_all + stamp head`` 快
路径——迁移文件里真正的 ``upgrade()`` DDL 从未在这条路径上执行过；只有
"legacy"路径（已存在、从未 stamp 过的旧库）才会跑
``create_all(补表) + stamp 到 baseline + upgrade head``，但生产上也没有
任何地方拿这条路径跑完后的 schema 去和 ORM 模型的最终形态做自动化比对。
一旦某次迁移漏写了字段/索引，或者 ORM 模型改了但配套迁移写错/漏写，只有
真实存量库跑 ``upgrade head`` 时才会暴露——这个测试把这类漂移提前到本地
/CI 里炸掉。

为什么不是"真正 0 表的空库直接跑 alembic upgrade head"：
链上最早的迁移 ``b3e502be1b9f_initial_schema.py`` 是历史上对着一个已经
``create_all`` 过的库做 autogenerate 生成的，内容全是
``batch_alter_table``/``create_index``，没有任何 ``create_table``——它
假设目标表已经存在，对着真正 0 表的库跑会在第一步就炸
``NoSuchTableError``。这不是本任务引入的问题，是这条迁移链从诞生起就有
的既成事实，``db/initializer.py`` 的 ``_LEGACY_BASELINE_REVISION`` 文档
也印证了同一点："旧库已经拥有 baseline 之前的完整 schema，只需要 stamp
到该 baseline，再 upgrade 剩下的修复迁移"。因此这里复用
``initializer.py`` 自己的 legacy 引导方式（``create_all`` 建表 + stamp
到 baseline + ``upgrade head``）让 baseline 之后的每一条迁移 DDL（含
Wave 1 新增的 notification_job 唯一索引迁移 ``0a513ac0e869``）都被真实
执行一遍，再和纯 ``create_all`` 的 schema 比较——这正是当前从未被自动化
验证过的那段迁移链。
"""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

from alembic import command
from app.core.config import Settings
from app.db.base import Base
from app.db.initializer import _LEGACY_BASELINE_REVISION

_REPO_ROOT = Path(__file__).resolve().parents[2]

# SQLite 方言下参与比较时需要排除的噪声项：
# - alembic_version：只有迁移路径会写这张表，create_all 路径不产生，是两条
#   路径的预期差异而非 schema 漂移；
# - news_fts 及其 FTS5 影子表（news_fts_data/idx/docsize/config）：由迁移
#   ec84dec88ae5 里的裸 SQL ``CREATE VIRTUAL TABLE ... USING fts5(...)``
#   创建，不通过 ORM 模型注册到 Base.metadata，create_all 天然不会建它们；
# - sqlite_ 前缀的系统表（如 sqlite_sequence）：SQLite 自己的内部记账表，
#   SQLAlchemy 的 inspector 通常已经默认过滤，这里保留一层防御性过滤，
#   不依赖该隐含行为。
_NOISE_TABLE_NAMES = {
    "alembic_version",
    "news_fts",
    "news_fts_data",
    "news_fts_idx",
    "news_fts_docsize",
    "news_fts_config",
}


def _build_alembic_config() -> Config:
    """独立构造 Alembic Config，脱离 app 启动上下文单独可用。

    与 ``test_notification_dedupe.py`` 里的写法保持一致：不直接导入
    ``db/initializer.py`` 的私有 ``_build_alembic_config``，避免测试之间
    通过私有实现细节耦合。
    """
    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "backend" / "alembic"))
    return config


def _is_noise_table(table_name: str) -> bool:
    return table_name in _NOISE_TABLE_NAMES or table_name.startswith("sqlite_")


def _snapshot_schema(engine: Engine) -> dict[str, dict[str, set[str]]]:
    """把一个引擎当前的 schema 摘要成 ``{表名: {"columns": {...}, "indexes": {...}}}``。

    索引名过滤掉 ``sqlite_autoindex_`` 前缀——SQLite 给无显式名字的 UNIQUE
    约束自动生成的隐式索引，其编号在 create_all 和迁移两条路径下可能不同，
    比较其存在性没有意义；SQLAlchemy 的 inspector 通常已经不会返回它们，
    这里防御性再过滤一次，不依赖该隐含行为。
    """
    inspector = inspect(engine)
    schema: dict[str, dict[str, set[str]]] = {}
    for table_name in inspector.get_table_names():
        if _is_noise_table(table_name):
            continue
        columns = {col["name"] for col in inspector.get_columns(table_name)}
        indexes = {
            idx["name"]
            for idx in inspector.get_indexes(table_name)
            if idx["name"] and not idx["name"].startswith("sqlite_autoindex_")
        }
        schema[table_name] = {"columns": columns, "indexes": indexes}
    return schema


def _format_diff(
    migrated: dict[str, dict[str, set[str]]], created: dict[str, dict[str, set[str]]]
) -> str:
    """把两份 schema 摘要的差异渲染成人可读的多行文本，方便定位漂移点。"""
    lines: list[str] = []
    migrated_tables = set(migrated)
    created_tables = set(created)

    only_migrated_tables = migrated_tables - created_tables
    only_created_tables = created_tables - migrated_tables
    if only_migrated_tables:
        lines.append(f"仅迁移链(upgrade head)产出的表: {sorted(only_migrated_tables)}")
    if only_created_tables:
        lines.append(f"仅 create_all 产出的表: {sorted(only_created_tables)}")

    for table in sorted(migrated_tables & created_tables):
        migrated_cols = migrated[table]["columns"]
        created_cols = created[table]["columns"]
        col_only_migrated = migrated_cols - created_cols
        col_only_created = created_cols - migrated_cols
        if col_only_migrated or col_only_created:
            lines.append(
                f"表 {table} 列差异: 仅迁移链={sorted(col_only_migrated)} "
                f"仅create_all={sorted(col_only_created)}"
            )

        migrated_idx = migrated[table]["indexes"]
        created_idx = created[table]["indexes"]
        idx_only_migrated = migrated_idx - created_idx
        idx_only_created = created_idx - migrated_idx
        if idx_only_migrated or idx_only_created:
            lines.append(
                f"表 {table} 索引差异: 仅迁移链={sorted(idx_only_migrated)} "
                f"仅create_all={sorted(idx_only_created)}"
            )

    return "\n".join(lines) if lines else "(两份 schema 摘要不 == 但未定位到具体差异，检查噪声过滤规则)"


def test_alembic_migration_chain_schema_matches_orm_metadata(tmp_path: Path, monkeypatch) -> None:
    """迁移链跑完 head 的最终 schema，必须和 ``Base.metadata.create_all`` 一致。

    两条独立的临时 SQLite 库：
    - ``created_all_engine``：纯 ``Base.metadata.create_all``，代表 ORM 模型
      当前认定的"正确"schema；
    - ``migrated_engine``：先 ``create_all``（模拟 legacy 库已有 baseline 之
      前的完整 schema，同 ``initializer.py`` 的假设），stamp 到
      ``_LEGACY_BASELINE_REVISION``，再真正执行 ``alembic upgrade head``——
      这一步会跑 baseline 之后的每一条迁移 DDL。

    两份 schema（表集合、每表列名集合、每表索引名集合，剔除上面列出的 SQLite
    噪声项后）逐项相等，任何差异都会在断言里输出可读 diff。
    """
    created_all_engine = create_engine(f"sqlite:///{tmp_path / 'create_all.db'}")
    Base.metadata.create_all(bind=created_all_engine)

    migrated_db_path = tmp_path / "migrated.db"
    migrated_url = f"sqlite:///{migrated_db_path}"

    bootstrap_engine = create_engine(migrated_url)
    Base.metadata.create_all(bind=bootstrap_engine)
    bootstrap_engine.dispose()

    # alembic/env.py 通过 app.core.config.get_settings().database_url 决定
    # 连接哪个库（不看调用方传进 Config 的 sqlalchemy.url），所以要让迁移
    # 命令连去临时库就必须 monkeypatch 这个入口——与
    # test_notification_dedupe.py / test_news_ingestion.py 里的既有写法一致。
    test_settings = Settings(database_url=migrated_url, seed_demo_data=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: test_settings)

    alembic_cfg = _build_alembic_config()
    command.stamp(alembic_cfg, _LEGACY_BASELINE_REVISION)
    command.upgrade(alembic_cfg, "head")

    migrated_engine = create_engine(migrated_url)

    migrated_schema = _snapshot_schema(migrated_engine)
    created_schema = _snapshot_schema(created_all_engine)

    migrated_engine.dispose()
    created_all_engine.dispose()

    assert migrated_schema == created_schema, _format_diff(migrated_schema, created_schema)
