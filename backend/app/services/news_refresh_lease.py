"""手动全源刷新 (/news/refresh) 的进程内 lease/cooldown。

与前端 60s 冷却对齐，避免多标签页或绕过前端节流时打爆抓取。
"""

from __future__ import annotations

import threading
import time

from app.core.config import get_settings

_lock = threading.Lock()
_lease_until_monotonic: float = 0.0


def reset_news_refresh_lease() -> None:
    """测试用：清空 lease。"""
    global _lease_until_monotonic
    with _lock:
        _lease_until_monotonic = 0.0


def try_acquire_news_refresh_lease() -> tuple[bool, float]:
    """尝试获取刷新 lease。

    Returns:
        (acquired, retry_after_seconds)：acquired=False 时 retry_after>0。
    """
    global _lease_until_monotonic
    cooldown = max(0.0, float(get_settings().news_refresh_cooldown_seconds))
    now = time.monotonic()
    with _lock:
        remaining = _lease_until_monotonic - now
        if remaining > 0:
            return False, remaining
        if cooldown <= 0:
            _lease_until_monotonic = 0.0
            return True, 0.0
        _lease_until_monotonic = now + cooldown
        return True, 0.0
