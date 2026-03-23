from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Event, Thread
from typing import Any


from app.repositories.worker_runtime_status_repository import WorkerRuntimeStatusRepository


class MarketQuoteProducer:
    worker_name = "market_quote_producer"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any],
        quote_service_factory: Callable[[], Any],
        event_bus: Any,
        poll_interval_seconds: float,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.quote_service_factory = quote_service_factory
        self.event_bus = event_bus
        self.poll_interval_seconds = max(poll_interval_seconds, 0.1)
        self.logger = logger or logging.getLogger(__name__)
        self._stop_event = Event()
        self._thread: Thread | None = None

    def run_cycle(self) -> None:
        try:
            with self.session_factory() as session:
                quotes = self.quote_service_factory().refresh_watchlist_quotes(session)
            if not quotes:
                with self.session_factory() as session:
                    WorkerRuntimeStatusRepository(session).record_success(
                        worker_name=self.worker_name,
                        quotes_count=0,
                    )
                return
            self.event_bus.publish(
                "market.watchlist_refreshed",
                {
                    "symbols": [str(quote.get("symbol")) for quote in quotes if quote.get("symbol")],
                    "quotes": quotes,
                },
            )
            with self.session_factory() as session:
                WorkerRuntimeStatusRepository(session).record_success(
                    worker_name=self.worker_name,
                    quotes_count=len(quotes),
                )
        except Exception as exc:
            with self.session_factory() as session:
                WorkerRuntimeStatusRepository(session).record_failure(
                    worker_name=self.worker_name,
                    error=str(exc),
                )
            self.logger.exception("market quote producer cycle failed")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, name="market-quote-producer", daemon=True)
        self._thread.start()

    def run_forever(self) -> None:
        self._stop_event.clear()
        self._run_loop()

    def stop(self, timeout: float | None = None) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_cycle()
            self._stop_event.wait(self.poll_interval_seconds)
