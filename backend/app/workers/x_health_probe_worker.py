"""后台 X(Twitter) 监控健康探针。

背景：`GET /health` 此前直接调用 `XMonitorService.provider_health()`，那会对
twitterapi.io 发起真实 HTTP 探针（`TWITTERAPI_IO_TIMEOUT_SECONDS` 线上配成 60，
而探针缓存 TTL 只有 30 秒）。`/health` 是前端轮询接口，等于每 30 秒就有一个请求
线程被最长 60 秒的外网调用占住，并且全程攥着一条 SQLite 连接 —— 这是"点一下没
反应"的成因之一。

修复把 `/health` 改成只读 `x_source_health` 的上次探测结果，但仓库里原本没有任何
组件定期写这张表（只有手动 `POST /api/x/refresh` 和按需的 `GET /api/health/x`
会写），于是 `/health` 会长期把健康的 X 监控报成 unknown。本 worker 补上这一环：
在后台线程里按固定间隔跑探针并落库，让 `/health` 既快又准。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.x_source_health_repository import XSourceHealthRepository
from app.services.ingestion.utils import _utc_now
from app.services.x_monitor.constants import PROVIDER_NAME
from app.services.x_monitor.service import XMonitorService
from app.workers.base_worker import BaseWorker

# 探针间隔：远小于 /health 判定陈旧的阈值（max(6h, cooldown*2)），保证记录始终新鲜；
# 又远大于 30 秒的旧 TTL，避免把下游 API 配额浪费在健康检查上。
DEFAULT_PROBE_INTERVAL_SECONDS = 600.0


class XHealthProbeWorker(BaseWorker):
    """定期探测 X 监控 provider 可用性并写入 `x_source_health`。"""

    worker_name = "x_health_probe"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        probe_interval_seconds: float = DEFAULT_PROBE_INTERVAL_SECONDS,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.probe_interval_seconds = max(probe_interval_seconds, 30.0)

    def get_interval(self) -> float:
        return self.probe_interval_seconds

    def do_cycle(self) -> int:
        settings = get_settings()
        if not settings.x_monitor_enabled or not settings.twitterapi_io_api_key:
            return 0

        started = time.perf_counter()
        # 网络探针刻意放在任何 session 之外：写事务绝不跨越外部 HTTP 调用，
        # 否则会在 SQLite 上持写锁跨越最长 60 秒的外网往返。
        try:
            with self.session_factory() as probe_session:
                healthy, detail = XMonitorService(probe_session).provider_health()
        except Exception as exc:  # 探针自身异常同样记为一次失败，不要让 worker 静默
            healthy, detail = False, f"{type(exc).__name__}: {exc}"
        latency_ms = round((time.perf_counter() - started) * 1000, 2)

        with self.session_factory() as session:
            health = XSourceHealthRepository(session).get_or_create(PROVIDER_NAME)
            health.total_fetches = (health.total_fetches or 0) + 1
            health.avg_latency_ms = latency_ms
            if healthy:
                health.last_success_at = _utc_now()
                health.consecutive_failures = 0
                health.last_error = None
            else:
                health.last_failure_at = _utc_now()
                health.total_failures = (health.total_failures or 0) + 1
                health.consecutive_failures = (health.consecutive_failures or 0) + 1
                health.last_error = detail
            session.commit()

        self.logger.info(
            "x health probe finished: healthy=%s detail=%s latency_ms=%s",
            healthy,
            detail,
            latency_ms,
        )
        return 1
