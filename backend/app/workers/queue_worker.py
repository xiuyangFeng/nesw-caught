from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.repositories.news_repository import NewsRepository
from app.repositories.worker_runtime_status_repository import WorkerRuntimeStatusRepository
from app.schemas.news import NewsItemSummary
from app.services import llm_providers, news_signal_pipeline
from app.services.event_bus import get_event_bus
from app.services.news_signal_pipeline import NewsSignalPipelineService
from app.services.notification_service import get_notification_service
from app.workers.base_worker import BaseWorker

# 全局内存分析任务队列
analysis_queue: queue.Queue[list[int]] = queue.Queue()

# 可观测性:通知入队失败(单批、不可恢复——这批通知草稿就此丢失,但不影响已
# 提交的新闻情感分析结果)历来只 log 一下就吞掉。这里加一个进程内累计计数,
# 由 BackgroundQueueWorker 周期性把增量回写到既有 worker_runtime_status 表。
_notification_metrics_lock = threading.Lock()
_notification_error_count = 0


def get_notification_error_count() -> int:
    with _notification_metrics_lock:
        return _notification_error_count


def _incr_notification_error() -> None:
    global _notification_error_count
    with _notification_metrics_lock:
        _notification_error_count += 1


# 各项被吞掉异常的计数,周期性(而非每轮)回写一次,避免给 worker_runtime_status
# 表带来额外的写放大。
_ERROR_METRICS_FLUSH_INTERVAL_SECONDS = 30.0


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
        # 被吞掉异常的计数回写节流(见 _maybe_flush_error_metrics)。
        self._next_error_metrics_flush_at = 0.0
        self._last_reported_error_counts: dict[str, int] = {}

    def get_interval(self) -> float:
        return self.poll_interval_seconds

    def _maybe_flush_error_metrics(self) -> None:
        """把 pipeline / llm_providers / event_bus 内被吞掉的异常计数,周期性地
        (而非每轮)以增量形式回写到既有 `worker_runtime_status` 表——每个类别单
        独一行(worker_name 形如 "background_queue_worker:crawl_error"),不复用
        本 worker 的主状态行,避免污染其 cycle_count/success_count 语义。

        这里只做"暴露计数",不改变任何一处原有的"单条/单批失败不影响整体"
        语义;不会因为这个失败而让 run_cycle 崩溃或抛出。
        """
        now = time.monotonic()
        if now < self._next_error_metrics_flush_at:
            return
        self._next_error_metrics_flush_at = now + _ERROR_METRICS_FLUSH_INTERVAL_SECONDS

        # 记账本身绝不能影响主循环:测试/部分场景里 session_factory 或
        # get_event_bus() 可能返回不完全实现真实接口的替身(如只实现部分方法
        # 的 Fake/Dummy),因此整段读取+回写都要兜底,保持与
        # BaseWorker._record_success/_record_failure 相同的"从不崩溃"契约。
        try:
            current_counts: dict[str, int] = {
                "crawl_error": news_signal_pipeline.get_pipeline_error_counts().get("crawl_error", 0),
                "notification_error": get_notification_error_count(),
            }
            for key, value in llm_providers.get_llm_provider_error_counts().items():
                current_counts[f"llm_{key}"] = value

            bus_status = get_event_bus().get_status()
            current_counts["event_handler_error"] = bus_status.local_handler_error_count
            current_counts["event_redis_publish_error"] = bus_status.redis_publish_error_count

            increased = {
                key: value - self._last_reported_error_counts.get(key, 0)
                for key, value in current_counts.items()
                if value > self._last_reported_error_counts.get(key, 0)
            }
            self._last_reported_error_counts = current_counts
            if not increased:
                return

            with self.session_factory() as session:
                repo = WorkerRuntimeStatusRepository(session)
                for key, delta in increased.items():
                    repo.record_failure(
                        worker_name=f"{self.worker_name}:{key}",
                        error=(
                            f"{delta} suppressed exception(s) since last flush "
                            f"(cumulative={current_counts[key]})"
                        ),
                    )
                session.commit()
        except Exception:
            self.logger.exception("Failed to flush suppressed-error metrics to worker_runtime_status")

    def do_cycle(self) -> int:
        """异步消化分析队列。"""
        self._maybe_flush_error_metrics()

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
                    # 不可恢复:这一批通知草稿的入队机会已经丢失(不会重试),但
                    # 不影响本轮已提交的情感分析结果,因此不改变整批处理的返回值/
                    # 语义,只补上计数使其可观测。
                    self.logger.exception(
                        "Failed to enqueue feishu notifications for %s news items",
                        len(notification_payloads),
                    )
                    _incr_notification_error()

        if summary.processed_count > 0:
            event_bus.publish(
                "news.signals_processed",
                {"news_ids": summary.news_ids, "processed_count": summary.processed_count},
            )

        return summary.processed_count
