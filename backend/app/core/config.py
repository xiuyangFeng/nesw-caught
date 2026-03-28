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
    event_bus_backend: str = "hybrid"
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_stream_news_ingested: str = "stream:news:ingested"
    redis_stream_news_processed: str = "stream:news:processed"
    redis_stream_market_watchlist: str = "stream:market:watchlist"
    redis_stream_maxlen: int = 1000
    event_bus_publish_timeout_seconds: float = 1.0
    ai_enabled: bool = False
    http_timeout_seconds: float = 10.0
    news_sources_file: str | None = None
    x_monitor_enabled: bool = False
    x_monitor_accounts_file: str | None = None
    twitterapi_io_api_key: str | None = None
    twitterapi_io_timeout_seconds: float = 60.0
    twitterapi_io_min_interval_seconds: float = 0.0
    x_monitor_refresh_cooldown_hours: int = 3
    x_radar_rules_file: str | None = None
    market_quote_provider: str = "yahoo_finance"
    market_quote_cache_ttl_seconds: int = 180
    market_quote_producer_enabled: bool = True
    market_quote_poll_interval_seconds: float = 15.0
    tavily_api_key: str | None = None
    stock_news_min_count: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
