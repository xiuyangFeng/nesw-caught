"""市场总览行情轮询 worker（计划任务 B7，设计文档八节）。

- 继承 ``BaseWorker``，心跳/异常记账全部复用基类；
- ``do_cycle()`` = ``MarketOverviewService.refresh_index_quotes``（指数/ETF 落
  ``price_snapshot``，内部遵守"先联网后写库"两阶段纪律）+ 东财板块进程内缓存
  刷新（失败仅记日志，不影响指数落库与周期记账）；
- ``get_interval()``：任一 overview 市场盘中按 ``poll_interval_seconds``（默认
  60s），us/cn/hk/kr/jp/eu 全部闭市时降频到 ``idle_poll_interval_seconds``
  （默认 300s），判定走 ``any_overview_market_open``；
- 不发布 event_bus 事件（前端走定时轮询，不需要 SSE 推送）；
- 与 ``MarketQuoteProducer``（自选股 15s 轮询）完全独立：不共享调用、不改其
  配置；两者都写 ``price_snapshot`` 但 symbol 集合不同（自选股 vs 指数），无冲突。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.board_provider import get_cached_industry_boards
from app.services.market_hours import any_overview_market_open
from app.services.market_overview_service import MarketOverviewService
from app.workers.base_worker import BaseWorker


class MarketOverviewProducer(BaseWorker):
    worker_name = "market_overview_producer"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        overview_service_factory: Callable[[], MarketOverviewService] | None = None,
        board_refresher: Callable[[], object] | None = None,
        poll_interval_seconds: float,
        idle_poll_interval_seconds: float | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.overview_service_factory = overview_service_factory or MarketOverviewService
        # 板块缓存刷新默认走 get_cached_industry_boards（TTL 内命中则不发请求，
        # 抓取失败内部已降级不抛异常）；注入点主要供测试替换。
        self.board_refresher = board_refresher or (
            lambda: get_cached_industry_boards(
                ttl_seconds=float(get_settings().market_board_cache_ttl_seconds)
            )
        )
        self.poll_interval_seconds = max(poll_interval_seconds, 0.1)
        # 闭市间隔缺省退化为盘中间隔，对齐 MarketQuoteProducer 的语义。
        self.idle_poll_interval_seconds = max(
            idle_poll_interval_seconds
            if idle_poll_interval_seconds is not None
            else self.poll_interval_seconds,
            self.poll_interval_seconds,
        )

    def get_interval(self) -> float:
        # 全部 overview 市场闭市时降频：指数价格不再变动，继续按盘中频率打
        # provider 只会消耗配额、抬高被限流概率。
        if any_overview_market_open():
            return self.poll_interval_seconds
        return self.idle_poll_interval_seconds

    def do_cycle(self) -> int:
        started = time.perf_counter()
        with self.session_factory() as session:
            records = self.overview_service_factory().refresh_index_quotes(session)
        # 板块刷新失败仅记日志：板块区有 stale/fetch_failed 降级语义兜底，
        # 不值得因此把指数落库周期记成失败。
        try:
            self.board_refresher()
        except Exception as exc:
            self.logger.warning("market overview board refresh failed: %s", exc)
        ok_count = sum(1 for record in records if record.status == "ok")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self.logger.info(
            "market overview refresh finished: quotes=%s ok=%s elapsed_ms=%s",
            len(records),
            ok_count,
            elapsed_ms,
        )
        return ok_count
