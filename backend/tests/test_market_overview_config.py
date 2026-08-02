"""市场总览相关配置项测试（计划任务 B2，core/config.py 新增）。

对应设计文档八节配置表：
- market_overview_producer_enabled（默认 True，单机单进程形态）
- market_overview_poll_interval_seconds（默认 60.0，盘中轮询）
- market_overview_idle_poll_interval_seconds（默认 300.0，全市场闭市降频）
- market_board_cache_ttl_seconds（默认 60，东财板块进程内缓存 TTL）
- market_overview_news_lookback_hours（默认 24，新闻情绪滚动窗口）
"""

from __future__ import annotations

from app.core.config import Settings


def test_market_overview_settings_defaults() -> None:
    settings = Settings()

    assert settings.market_overview_producer_enabled is True
    assert settings.market_overview_poll_interval_seconds == 60.0
    assert settings.market_overview_idle_poll_interval_seconds == 300.0
    assert settings.market_board_cache_ttl_seconds == 60
    assert settings.market_overview_news_lookback_hours == 24


def test_market_overview_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_OVERVIEW_PRODUCER_ENABLED", "false")
    monkeypatch.setenv("MARKET_OVERVIEW_POLL_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("MARKET_OVERVIEW_IDLE_POLL_INTERVAL_SECONDS", "600")
    monkeypatch.setenv("MARKET_BOARD_CACHE_TTL_SECONDS", "120")
    monkeypatch.setenv("MARKET_OVERVIEW_NEWS_LOOKBACK_HOURS", "48")

    settings = Settings()

    assert settings.market_overview_producer_enabled is False
    assert settings.market_overview_poll_interval_seconds == 30.0
    assert settings.market_overview_idle_poll_interval_seconds == 600.0
    assert settings.market_board_cache_ttl_seconds == 120
    assert settings.market_overview_news_lookback_hours == 48
