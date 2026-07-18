from __future__ import annotations

import logging
import queue
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsItemSummary
from app.services.event_bus import get_event_bus
from app.services.news_signal_pipeline import NewsSignalPipelineService
from app.services.notification_service import get_notification_service
from app.workers.base_worker import BaseWorker

# 全局内存分析任务队列
analysis_queue: queue.Queue[list[int]] = queue.Queue()


class BackgroundQueueWorker(BaseWorker):
    worker_name = "background_queue_worker"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        poll_interval_seconds: float = 1.0,
        fallback_scan_interval_seconds: float = 30.0,
        heartbeat_interval_seconds: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(
            session_factory=session_factory,
            logger=logger,
            # 空转周期的心跳写事务降频(在 BaseWorker 统一实现),避免每秒一次的无意义写放大。
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )
        self.poll_interval_seconds = poll_interval_seconds
        # 兜底扫描是无索引可用的 Pending 全表查询,不需要每秒执行一次。
        self.fallback_scan_interval_seconds = fallback_scan_interval_seconds
        self._next_fallback_scan_at = 0.0

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

        # 自愈兜底：如果内存队列为空，定期(而非每个轮询周期)去数据库拉取 Pending 新闻
        if not batch_ids:
            now = time.monotonic()
            if now < self._next_fallback_scan_at:
                return 0
            self._next_fallback_scan_at = now + self.fallback_scan_interval_seconds
            with self.session_factory() as session:
                pipeline = NewsSignalPipelineService(session, session_factory=self.session_factory)
                pending = pipeline.list_pending_news_ids(limit=50)
                batch_ids.update(pending)

        if not batch_ids:
            return 0

        target_ids = list(batch_ids)
        self.logger.info("Background queue processing analysis for news IDs: %s", target_ids)

        event_bus = get_event_bus()
        notification_service = get_notification_service()

        with self.session_factory() as session:
            # 1. 执行重负载管线 (LLM 调用在写事务之外的纯内存阶段完成)
            pipeline = NewsSignalPipelineService(session, session_factory=self.session_factory)
            summary = pipeline.process_news_ids(target_ids)

            # 2. 批量加载新闻实体 (N+1 修复)
            news_repo = NewsRepository(session)
            items = news_repo.get_by_ids(summary.news_ids)

            update_payloads = []
            for item in items:
                payload = NewsItemSummary.model_validate(item, from_attributes=True).model_dump(mode="json")
                payload["updated_fields"] = ["sentiment_label"]
                update_payloads.append((item, payload))

            session.commit()

            # 3. 广播已评分事件，并批量进行通知草稿入队(一次配置加载 + 一次提交)
            notification_payloads = []
            for item, payload in update_payloads:
                event_bus.publish("news.updated", payload)
                notification_payloads.append(
                    {
                        "title": item.title,
                        "summary": item.summary,
                        "source_name": item.source_name,
                        "market": item.market,
                        "published_at": item.published_at.isoformat() if item.published_at else None,
                    }
                )
            if notification_payloads:
                try:
                    notification_service.on_news_created_batch(notification_payloads)
                except Exception:
                    self.logger.exception(
                        "Failed to enqueue feishu notifications for %s news items",
                        len(notification_payloads),
                    )

        if summary.processed_count > 0:
            event_bus.publish(
                "news.signals_processed",
                {"news_ids": summary.news_ids, "processed_count": summary.processed_count},
            )

        return summary.processed_count
