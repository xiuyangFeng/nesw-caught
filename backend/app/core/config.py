from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "News Caught Backend"
    environment: str = "development"
    api_prefix: str = "/api"
    log_level: str = "INFO"
    database_url: str = Field(
        default=f"sqlite:///{Path(__file__).resolve().parents[2] / 'data' / 'app.db'}"
    )
    stream_mode: str = "sse"
    ai_enabled: bool = False
    http_timeout_seconds: float = 10.0
    news_sources_file: str | None = None
    x_monitor_enabled: bool = False
    grok_bridge_base_url: str | None = None
    grok_bridge_timeout_seconds: float = 60.0
    x_monitor_accounts_file: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
