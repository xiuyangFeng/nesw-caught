from __future__ import annotations

import logging
from collections.abc import Callable
from sqlalchemy.orm import Session
from app.workers.base_worker import BaseWorker


class NotificationDeliveryWorker(BaseWorker):
    worker_name = "notification_delivery_worker"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        notification_service: Any,
        poll_interval_seconds: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.notification_service = notification_service
        self.poll_interval_seconds = max(poll_interval_seconds, 0.1)

    def get_interval(self) -> float:
        return self.poll_interval_seconds

    def do_cycle(self) -> int:
        """运行一次派发 cycle,返回成功派发的 job 数量。"""
        return self.notification_service._delivery_tick()
