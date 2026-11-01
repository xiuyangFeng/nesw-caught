"""聚焦改造 P3 迁移测试：单价列改为每百万 token（数值保留），AI 漏斗新表可往返。"""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.core.config import Settings
from app.db.base import Base

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NEW_TABLES = {
    "news_ai_screen",
    "news_ai_analysis",
    "news_impact",
    "impact_correction",
    "stock_sector",
    "focus_sector_override",
}


def _alembic_config() -> Config:
    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "backend" / "alembic"))
    config.attributes["configure_logger"] = False
    return config


def test_p3_migrations_round_trip_and_keep_prices(tmp_path: Path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'p3.db'}"
    test_settings = Settings(database_url=db_url, seed_demo_data=False)
    monkeypatch.setattr("app.core.config.get_settings", lambda: test_settings)
    config = _alembic_config()

    # 模拟 P2 时的库：create_all 后把单价列改回旧名、删掉 P3 新表，再 stamp 到 P2 head。
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE llm_provider_config RENAME COLUMN input_price_per_1m TO input_price_per_1k"))
        connection.execute(
            text("ALTER TABLE llm_provider_config RENAME COLUMN output_price_per_1m TO output_price_per_1k")
        )
        for table in _NEW_TABLES:
            connection.execute(text(f"DROP TABLE {table}"))
        connection.execute(
            text(
                "INSERT INTO llm_provider_config (provider_name, model_name, api_key, is_active, is_default, "
                "input_price_per_1k, output_price_per_1k, created_at, updated_at) "
                "VALUES ('deepseek', 'deepseek-v4-flash', 'enc', 1, 0, 0.02, 1.0, '2026-11-01', '2026-11-01')"
            )
        )
    engine.dispose()

    command.stamp(config, "c6d2f8a4e9b1")
    command.upgrade(config, "head")
    engine = create_engine(db_url)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("llm_provider_config")}
    assert {"input_price_per_1m", "output_price_per_1m"} <= columns
    assert not {"input_price_per_1k", "output_price_per_1k"} & columns
    assert _NEW_TABLES <= set(inspector.get_table_names())
    with engine.connect() as connection:
        prices = connection.execute(
            text("SELECT input_price_per_1m, output_price_per_1m FROM llm_provider_config")
        ).one()
    engine.dispose()
    assert tuple(prices) == (0.02, 1.0)

    command.downgrade(config, "c6d2f8a4e9b1")
    engine = create_engine(db_url)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("llm_provider_config")}
    assert {"input_price_per_1k", "output_price_per_1k"} <= columns
    assert not _NEW_TABLES & set(inspector.get_table_names())
    engine.dispose()
