from __future__ import annotations

import logging
import queue
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session
from app.workers.base_worker import BaseWorker
from app.services.news_signal_pipeline import NewsSignalPipelineService
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsItemSummary
from app.services.event_bus import get_event_bus
from app.services.notification_service import NotificationService


# 全局内存分析任务队列
analysis_queue: queue.Queue[list[int]] = queue.Queue()


class BackgroundQueueWorker(BaseWorker):
    worker_name = "background_queue_worker"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        poll_interval_seconds: float = 1.0,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.poll_interval_seconds = poll_interval_seconds

    def get_interval(self) -> float:
        return self.poll_interval_seconds

    def do_cycle(self) -> int:
        """异步消化分析队列。"""
        batch_ids: set[int] = set()
        while not self._stop_event.is_set():
            try:
                # 非阻塞获取
                news_ids = analysis_queue.get_nowait()
                batch_ids.update(news_ids)
                analysis_queue.task_done()
            except queue.Empty:
                break

        if not batch_ids:
            return 0

        target_ids = list(batch_ids)
        self.logger.info("Background queue processing analysis for news IDs: %s", target_ids)

        # 动态导入，避免循环引用
        from app.main import get_notification_service
        event_bus = get_event_bus()
        notification_service = get_notification_service()

        with self.session_factory() as session:
            # 1. 执行重负载管线 (包含大模型调用)
            summary = NewsSignalPipelineService(session).process_news_ids(target_ids)

            # 2. 批量加载新闻实体 (N+1 修复)
            news_repo = NewsRepository(session)
            items = news_repo.get_by_ids(summary.news_ids)

            update_payloads = []
            for item in items:
                payload = NewsItemSummary.model_validate(item, from_attributes=True).model_dump(mode="json")
                payload["updated_fields"] = ["sentiment_label"]
                update_payloads.append((item, payload))

            session.commit()

            # 3. 广播已评分事件，并进行通知草稿入队
            for item, payload in update_payloads:
                event_bus.publish("news.updated", payload)
                try:
                    notification_service.on_news_created(
                        {
                            "title": item.title,
                            "summary": item.summary,
                            "source_name": item.source_name,
                            "market": item.market,
                            "published_at": item.published_at.isoformat() if item.published_at else None,
                        }
                    )
                except Exception:
                    self.logger.exception("Failed to enqueue feishu notification for news id %s", item.id)

        if summary.processed_count > 0:
            event_bus.publish(
                "news.signals_processed",
                {"news_ids": summary.news_ids, "processed_count": summary.processed_count},
            )

        return summary.processed_count
