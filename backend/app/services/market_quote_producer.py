from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.services.market_hours import any_market_open
from app.workers.base_worker import BaseWorker


class MarketQuoteProducer(BaseWorker):
    worker_name = "market_quote_producer"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        quote_service_factory: Callable[[], Any],
        event_bus: Any,
        poll_interval_seconds: float,
        idle_poll_interval_seconds: float | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.quote_service_factory = quote_service_factory
        self.event_bus = event_bus
        self.poll_interval_seconds = max(poll_interval_seconds, 0.1)
        # 闭市间隔缺省退化为盘中间隔，保持既有调用方（只传 poll_interval_seconds）
        # 的行为完全不变。
        self.idle_poll_interval_seconds = max(
            idle_poll_interval_seconds if idle_poll_interval_seconds is not None else self.poll_interval_seconds,
            self.poll_interval_seconds,
        )

    def get_interval(self) -> float:
        # 全市场闭市时降频：价格不再变动，继续按盘中频率打 provider 只会消耗配额。
        if any_market_open():
            return self.poll_interval_seconds
        return self.idle_poll_interval_seconds

    def do_cycle(self) -> int:
        started = time.perf_counter()
        self.logger.info("market quote refresh started")
        with self.session_factory() as session:
            # force=True：绕过读路径的 180s 缓存 TTL。producer 就是行情的生产者，
            # 若它也吃缓存，整个轮询链路的实际更新周期会退化成 TTL 而不是轮询间隔。
            quotes = self.quote_service_factory().refresh_watchlist_quotes(session, force=True)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        if not quotes:
            self.logger.info("market quote refresh finished: quotes=0 elapsed_ms=%s", elapsed_ms)
            return 0
        self.event_bus.publish(
            "market.watchlist_refreshed",
            {
                "symbols": [str(quote.get("symbol")) for quote in quotes if quote.get("symbol")],
                "quotes": quotes,
            },
        )
        self.logger.info(
            "market quote refresh finished: quotes=%s elapsed_ms=%s", len(quotes), elapsed_ms
        )
        return len(quotes)
