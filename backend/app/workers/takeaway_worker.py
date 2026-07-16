"""Takeaway 补齐 Worker:消化 takeaway_queue,受批量/日上限约束地生成一句话结论。"""
from __future__ import annotations

import queue
from collections.abc import Callable
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.news import NewsItemSummary
from app.services.event_bus import get_event_bus
from app.services.news_takeaway import NewsTakeawayService, takeaway_queue
from app.workers.base_worker import BaseWorker


class TakeawayWorker(BaseWorker):
    worker_name = "takeaway_worker"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        poll_interval_seconds: float | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory)
        self.poll_interval_seconds = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else get_settings().takeaway_poll_interval_seconds
        )
        # 日配额为进程内计数,重启即重置——单机自用场景下的简单护栏
        self._generated_on: date | None = None
        self._generated_count = 0

    def get_interval(self) -> float:
        return self.poll_interval_seconds

    def _remaining_daily_quota(self) -> int:
        today = date.today()
        if self._generated_on != today:
            self._generated_on = today
            self._generated_count = 0
        return max(0, get_settings().takeaway_daily_limit - self._generated_count)

    def _drain_queue(self) -> set[int]:
        batch_ids: set[int] = set()
        while not self._stop_event.is_set():
            try:
                batch_ids.update(takeaway_queue.get_nowait())
                takeaway_queue.task_done()
            except queue.Empty:
                break
        return batch_ids

    def do_cycle(self) -> int:
        settings = get_settings()
        if not settings.ai_enabled:
            # AI 关闭时抽干队列丢弃,避免堆积
            self._drain_queue()
            return 0

        batch_ids = self._drain_queue()
        if not batch_ids:
            return 0

        quota = self._remaining_daily_quota()
        if quota <= 0:
            self.logger.warning("takeaway daily limit reached, dropping %s candidates", len(batch_ids))
            return 0

        batch_limit = min(settings.takeaway_batch_limit, quota)
        event_bus = get_event_bus()
        with self.session_factory() as session:
            service = NewsTakeawayService(session)
            updated = service.generate_for_ids(sorted(batch_ids), batch_limit=batch_limit)
            payloads = [
                {
                    **NewsItemSummary.model_validate(item, from_attributes=True).model_dump(mode="json"),
                    "updated_fields": ["ai_takeaway"],
                }
                for item in updated
            ]
            updated_ids = [item.id for item in updated]
            session.commit()

        self._generated_count += len(updated_ids)
        for payload in payloads:
            event_bus.publish("news.updated", payload)
        if updated_ids:
            event_bus.publish(
                "news.signals_processed",
                {"news_ids": updated_ids, "processed_count": len(updated_ids)},
            )
        return len(updated_ids)
