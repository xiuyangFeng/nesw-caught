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
    llm_timeout_seconds: float = 60.0
    news_sources_file: str | None = None
    news_scheduler_enabled: bool = False
    news_scheduler_tick_seconds: float = 5.0
    news_backoff_max_multiplier: int = 8
    x_monitor_enabled: bool = False
    x_monitor_accounts_file: str | None = None
    twitterapi_io_api_key: str | None = None
    twitterapi_io_timeout_seconds: float = 60.0
    twitterapi_io_min_interval_seconds: float = 0.0
    x_monitor_refresh_cooldown_hours: int = 3
    x_radar_rules_file: str | None = None
    market_quote_provider: str = "yahoo_finance"
    market_quote_cache_ttl_seconds: int = 180
    # 财报/事件日历缓存 TTL：yfinance 日历调用慢，默认 6 小时。
    calendar_cache_ttl_seconds: int = 21600
    market_quote_producer_enabled: bool = True
    market_quote_poll_interval_seconds: float = 15.0
    tavily_api_key: str | None = None
    stock_news_min_count: int = 3
    data_cleanup_enabled: bool = True
    data_cleanup_interval_seconds: float = 86400.0
    data_cleanup_vacuum_interval_seconds: float = 604800.0
    news_item_retention_days: int = 180
    article_content_retention_days: int = 90
    price_snapshot_retention_days: int = 30
    dedup_secondary_judge: str | None = None
    # 情绪/利好利空评测金标集路径；缺省时用 backend/data/research 内置金标。
    sentiment_eval_dataset_file: str | None = None
    # Seed demo/example data (watchlist, news, X posts...) into an empty database
    # at startup. Defaults to True so local dev (scripts/dev.sh) and the test
    # suite keep their out-of-the-box demo experience; set SEED_DEMO_DATA=false
    # in production. Standalone seeding: `python scripts/seed_demo_data.py`.
    seed_demo_data: bool = True
    # Require X-App-Token verification on protected API routes. The test suite
    # disables this globally in backend/tests/conftest.py (VERIFY_APP_TOKEN=false)
    # instead of relying on runtime pytest detection.
    verify_app_token: bool = True
    # Enable the in-process TTL caches on read-heavy news routes. Disabled by
    # the test suite (ROUTE_CACHE_ENABLED=false) except in dedicated cache tests.
    route_cache_enabled: bool = True
    # Token usage buffer batching: flush to DB every N rows or after this many
    # seconds. Tests set TOKEN_USAGE_FLUSH_N=1 for synchronous persistence.
    token_usage_flush_n: int = 50
    token_usage_flush_secs: float = 10.0
    # 每日盘前/盘后 AI 简报（Daily Digest）：定时用 LLM 生成结构化简报并推送。
    # digest_enabled 默认关闭，避免未配置 LLM/飞书的环境无谓触发；开启后由
    # DigestWorker 按各市场本地时区在盘前/盘后时点生成推送。
    digest_enabled: bool = False
    digest_premarket_time: str = "08:30"
    digest_postmarket_time: str = "16:30"
    digest_lookback_hours: int = 16
    # Reuse a cached classification result when the same (normalized) content is
    # classified again, skipping the LLM call and token accounting entirely.
    # Tests toggle this to assert both cached and uncached behavior.
    llm_classification_cache_enabled: bool = True

    # ---------------------------------------------------------------------
    # 告警治理（去重 / 免打扰 / 分级 / 合并摘要）——全部默认保守（关闭），
    # 不配置时行为与旧版一致，避免惊到既有测试。前端可在通知设置页覆盖，
    # 覆盖值只保存在 NotificationService 内存里（不落库、无迁移）。
    # ---------------------------------------------------------------------
    # 免打扰时段，"HH:MM" 24 小时制；start/end 任一为空即视为未启用。
    notify_quiet_hours_start: str | None = None
    notify_quiet_hours_end: str | None = None
    # 免打扰时段判定所用时区（复用 zoneinfo）。
    notify_quiet_hours_tz: str = "Asia/Shanghai"
    # 同 symbol / 同事件在 N 分钟窗口内只发一次；0 = 关闭去重窗口。
    notify_dedupe_window_minutes: int = 0
    # 合并摘要窗口：非 critical 告警先暂存 N 分钟再合并；0 = 关闭合并。
    notify_digest_window_minutes: int = 0
    # 合并阈值：窗口内累计达到该条数才合并成摘要，否则逐条发送。
    notify_digest_threshold: int = 3
    # 自选股异动升级为 critical 的涨跌幅绝对值阈值（%）。
    notify_critical_change_percent: float = 8.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
