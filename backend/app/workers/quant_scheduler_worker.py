"""量化盘后调度 worker：交易日到达 run_at 后执行一次当日任务（增量回填 + 流水线）。

单进程形态随后端 lifespan 启停；独立入口供多进程部署：

    PYTHONPATH=backend python -m app.workers.quant_scheduler_worker

环境变量：
- QUANT_SCHEDULER_ENABLED  是否随后端进程启停（默认 true，见 settings）
- QUANT_SCHEDULER_RUN_AT   每日触发时刻 HH:MM（默认 16:30）
- QUANT_SCHEDULER_TICK_SECONDS  轮询间隔（默认 60）
- QUANT_SCHEDULER_BACKFILL_LIMIT  单日增量回填标的数上限（默认 50，防东财限流）
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.db.initializer import initialize_database
from app.db.market_initializer import initialize_market_database
from app.db.session import SessionLocal
from app.services.event_bus import build_event_bus, set_event_bus
from app.services.quant.scheduler import QuantScheduler
from app.workers.base_worker import BaseWorker


class QuantSchedulerWorker(BaseWorker):
    worker_name = "quant_scheduler"

    def __init__(
        self,
        *,
        session_factory,
        logger: logging.Logger | None = None,
        tick_seconds: float = 60.0,
        run_at: str = "16:30",
        backfill_limit: int = 50,
        sleep_seconds: float = 0.4,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.tick_seconds = tick_seconds
        self.scheduler = QuantScheduler(
            session_factory=session_factory,
            logger=logger,
            run_at=run_at,
            backfill_limit=backfill_limit,
            sleep_seconds=sleep_seconds,
            include_financials=True,
        )

    def get_interval(self) -> float:
        return self.tick_seconds

    def do_cycle(self) -> int:
        if not self.scheduler.should_run():
            return 0
        result = self.scheduler.run_daily_task()
        self.logger.info("quant scheduled daily task completed: %s", result)
        return 1


def build_quant_scheduler_worker() -> QuantSchedulerWorker:
    settings = get_settings()
    return QuantSchedulerWorker(
        session_factory=SessionLocal,
        tick_seconds=settings.quant_scheduler_tick_seconds,
        run_at=settings.quant_scheduler_run_at,
        backfill_limit=settings.quant_scheduler_backfill_limit,
    )


def main() -> None:
    initialize_database()
    initialize_market_database()
    set_event_bus(build_event_bus())
    worker = build_quant_scheduler_worker()
    worker.run_forever()


if __name__ == "__main__":
    main()
