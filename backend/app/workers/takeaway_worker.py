"""Takeaway 补齐 Worker:消化 takeaway_queue,受批量/日上限约束地生成一句话结论。"""
from __future__ import annotations

import queue
import time
from collections.abc import Callable
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.news_item import NewsItem
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
        fallback_scan_interval_seconds: float | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory)
        settings = get_settings()
        self.poll_interval_seconds = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else settings.takeaway_poll_interval_seconds
        )
        # DB 兜底扫描间隔;<= 0 关闭（默认关闭,保持单进程形态的既有语义）。
        # 见 config.takeaway_fallback_scan_interval_seconds 的说明:多进程形态下
        # `takeaway_queue` 的生产者（feed layout）留在 web 进程,独立进程里的本
        # worker 只能靠这条兜底扫描拿到活。
        self.fallback_scan_interval_seconds = float(
            fallback_scan_interval_seconds
            if fallback_scan_interval_seconds is not None
            else settings.takeaway_fallback_scan_interval_seconds
        )
        self._next_fallback_scan_at = 0.0
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

    def _fallback_scan(self, *, limit: int) -> set[int]:
        """事件/队列通路不可用时的 DB 兜底扫描（按间隔节流）。

        只挑「信号管线已处理完（signal_status 非空）但仍缺 takeaway」的条目,
        按发布时间倒序取最近的 N 条——与 feed layout 的候选口径并不完全一致
        （那里按编辑分 top 20% 精选）,但兜底扫描的目的只是保证多进程形态下
        takeaway 不会彻底停摆;真实的 LLM 用量仍由 takeaway_batch_limit /
        takeaway_daily_limit 两道既有闸门封顶。
        """
        if self.fallback_scan_interval_seconds <= 0:
            return set()
        now = time.monotonic()
        if now < self._next_fallback_scan_at:
            return set()
        self._next_fallback_scan_at = now + self.fallback_scan_interval_seconds
        stmt = (
            select(NewsItem.id)
            .where(NewsItem.ai_takeaway.is_(None), NewsItem.signal_status.is_not(None))
            .order_by(
                NewsItem.published_at.is_(None).asc(),
                NewsItem.published_at.desc(),
                NewsItem.id.desc(),
            )
            .limit(limit)
        )
        with self.session_factory() as session:
            return set(session.scalars(stmt))

    def do_cycle(self) -> int:
        settings = get_settings()
        if not settings.ai_enabled:
            # AI 关闭时抽干队列丢弃,避免堆积
            self._drain_queue()
            return 0

        batch_ids = self._drain_queue()
        if not batch_ids:
            batch_ids = self._fallback_scan(limit=settings.takeaway_batch_limit)
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

        # updated_ids 是「拿到 LLM 响应的尝试数」(含空字符串结论),非「非空结论数」——
        # 语义与 news_takeaway.generate_for_ids 对齐,确保日配额约束的是实际 LLM 调用量。
        self._generated_count += len(updated_ids)
        for payload in payloads:
            event_bus.publish("news.updated", payload)
        if updated_ids:
            event_bus.publish(
                "news.signals_processed",
                {"news_ids": updated_ids, "processed_count": len(updated_ids)},
            )
        return len(updated_ids)
