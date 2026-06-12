from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Event, Thread
from typing import Any


from sqlalchemy.orm import Session
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
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.quote_service_factory = quote_service_factory
        self.event_bus = event_bus
        self.poll_interval_seconds = max(poll_interval_seconds, 0.1)

    def get_interval(self) -> float:
        return self.poll_interval_seconds

    def do_cycle(self) -> int:
        with self.session_factory() as session:
            quotes = self.quote_service_factory().refresh_watchlist_quotes(session)
        if not quotes:
            return 0
        self.event_bus.publish(
            "market.watchlist_refreshed",
            {
                "symbols": [str(quote.get("symbol")) for quote in quotes if quote.get("symbol")],
                "quotes": quotes,
            },
        )
        return len(quotes)
