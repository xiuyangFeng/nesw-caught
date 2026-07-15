"""每日盘前/盘后 AI 简报定时 worker。

按各市场本地时区（港股 Asia/Hong_Kong、美股 America/New_York）在配置的盘前/盘后
时点触发简报生成与推送。采用"每分钟 tick 检查是否到达今天尚未触发的时点"的幂等
方式：每个 (市场, 阶段, 本地日期) 组合每天最多触发一次，避免重复推送。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.workers.base_worker import BaseWorker

# (市场范围, 阶段, 时区名)。触发时点由 premarket_time / postmarket_time 提供。
_MARKET_ZONES: list[tuple[str, str, str]] = [
    ("hk", "premarket", "Asia/Hong_Kong"),
    ("hk", "postmarket", "Asia/Hong_Kong"),
    ("us", "premarket", "America/New_York"),
    ("us", "postmarket", "America/New_York"),
]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hour_str, minute_str = value.strip().split(":", 1)
        hour, minute = int(hour_str), int(minute_str)
        if 0 <= hour < 24 and 0 <= minute < 60:
            return hour, minute
    except (ValueError, AttributeError):
        pass
    return 8, 30


class DigestWorker(BaseWorker):
    worker_name = "digest_worker"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        trigger_fn: Callable[[str, str], None],
        premarket_time: str = "08:30",
        postmarket_time: str = "16:30",
        grace_minutes: int = 10,
        tick_seconds: float = 60.0,
        now_factory: Callable[[], datetime] = _utc_now,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.trigger_fn = trigger_fn
        self.premarket_time = premarket_time
        self.postmarket_time = postmarket_time
        self.grace_minutes = max(1, int(grace_minutes))
        self.tick_seconds = max(1.0, float(tick_seconds))
        self.now_factory = now_factory
        # dedupe：记录每个 (市场:阶段) 最近一次已触发的本地日期，保证当天只触发一次。
        self._fired: dict[str, str] = {}

    def get_interval(self) -> float:
        return self.tick_seconds

    def _time_for_phase(self, phase: str) -> str:
        return self.premarket_time if phase == "premarket" else self.postmarket_time

    def do_cycle(self) -> int:
        now_utc = self.now_factory()
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=UTC)

        fired_count = 0
        for market, phase, zone_name in _MARKET_ZONES:
            local_now = now_utc.astimezone(ZoneInfo(zone_name))
            hour, minute = _parse_hhmm(self._time_for_phase(phase))
            target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            local_date = local_now.date().isoformat()
            dedupe_key = f"{market}:{phase}"

            if self._fired.get(dedupe_key) == local_date:
                continue

            # 到达时点后 grace_minutes 内触发一次；超窗则等次日（避免进程晚启后补发陈旧简报）。
            if target <= local_now < target + timedelta(minutes=self.grace_minutes):
                self._fired[dedupe_key] = local_date
                try:
                    self.trigger_fn(market, phase)
                    fired_count += 1
                    self.logger.info("digest triggered: market=%s phase=%s date=%s", market, phase, local_date)
                except Exception:
                    self.logger.exception("digest trigger failed: market=%s phase=%s", market, phase)

        return fired_count
