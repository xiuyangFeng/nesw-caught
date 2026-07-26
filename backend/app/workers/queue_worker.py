from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
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

# 租约兜底默认值(settings 不可用时使用)
DEFAULT_INFLIGHT_LEASE_SECONDS = 600.0
DEFAULT_BACKLOG_BATCH_SIZE = 50
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_FALLBACK_SCAN_INTERVAL_SECONDS = 30.0
# 持续故障时 _record_failure 的写库节流(避免 1s 一次写 worker_runtime_status)。
FAILURE_RECORD_MIN_INTERVAL_SECONDS = 30.0


class InflightLeaseRegistry:
    """"已领取但尚未回写 signal_status"的 news_id 进程内租约表。

    背景(P0 跨轮重复消费):`NewsIngestScheduler._drain_signal_backlog` 每个 tick
    (默认 5s)都会把 `signal_status IS NULL` 的前 N 条塞进 `analysis_queue`,而
    `signal_status` 只在管线阶段 2b 提交时才变成 "processed"。批次耗时 > tick
    (要爬正文 + 跑 LLM,几乎必然)时,同一批 id 会被反复投递,下一轮整批重跑:
    重复爬正文 + 双倍 LLM token。此前"单入口"注释只解决了"两个组件同时处理",
    没有解决"同一组件跨轮重复领取"。

    这里用租约把在处理中的 id 挡在投递入口之外:
    - `acquire()`:投递方(scheduler)领取,已在租约内的 id 不再返回;
    - `touch()`:消费方(queue worker)真正开始处理时续租,兜住"经由
      news.created_batch 直接入队、没走 acquire"的那条路径;
    - `release()`:处理完成/失败后立即释放,失败的条目下一轮可以重试;
    - 租约超时(默认 600s)后自动过期,防止 worker 崩溃导致条目永久漏处理。

    该对象被 scheduler 与 queue worker 两个不同实例共享(模块级单例
    `analysis_inflight`),所以状态必须放在这里而不是任何一方的实例上。
    """

    def __init__(
        self,
        *,
        lease_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._lease_seconds = lease_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._leases: dict[int, float] = {}

    @property
    def lease_seconds(self) -> float:
        if self._lease_seconds is not None:
            return float(self._lease_seconds)
        try:
            return float(get_settings().news_inflight_lease_seconds)
        except Exception:  # pragma: no cover - 配置不可用时退回默认值
            return DEFAULT_INFLIGHT_LEASE_SECONDS

    def _purge_locked(self, now: float) -> None:
        ttl = self.lease_seconds
        expired = [news_id for news_id, granted_at in self._leases.items() if now - granted_at >= ttl]
        for news_id in expired:
            self._leases.pop(news_id, None)

    def acquire(self, news_ids: list[int], *, limit: int | None = None) -> list[int]:
        """领取租约,返回本次真正拿到租约的 id(已在租约内的会被过滤掉)。

        `limit` 用于限制单次领取量:必须在这里截断而不是对返回值切片,否则被切掉
        的那部分会白白占着租约却没人处理,直到租约过期(600s)前都不会再被投递。
        """
        now = self._clock()
        granted: list[int] = []
        with self._lock:
            self._purge_locked(now)
            for news_id in news_ids:
                if limit is not None and len(granted) >= limit:
                    break
                if news_id in self._leases:
                    continue
                self._leases[news_id] = now
                granted.append(news_id)
        return granted

    def touch(self, news_ids: list[int]) -> None:
        """无条件(重新)计时:消费方开始处理时调用,租约从此刻起算。"""
        now = self._clock()
        with self._lock:
            self._purge_locked(now)
            for news_id in news_ids:
                self._leases[news_id] = now

    def release(self, news_ids: list[int]) -> None:
        with self._lock:
            for news_id in news_ids:
                self._leases.pop(news_id, None)

    def active_ids(self) -> set[int]:
        now = self._clock()
        with self._lock:
            self._purge_locked(now)
            return set(self._leases)

    def active_count(self) -> int:
        return len(self.active_ids())

    def clear(self) -> None:
        with self._lock:
            self._leases.clear()


# 模块级单例:scheduler(投递方)与 BackgroundQueueWorker(消费方)共享同一份租约状态。
analysis_inflight = InflightLeaseRegistry()


def _safe_settings():
    """读取配置;测试等场景下配置不可用时返回 None,由调用方退回硬编码默认值。"""
    try:
        return get_settings()
    except Exception:  # pragma: no cover - 配置不可用是极端情况
        return None


def _resolve(explicit, settings, attr: str, default: float):
    """显式入参 > settings > 模块级默认值。"""
    if explicit is not None:
        return explicit
    if settings is not None:
        return getattr(settings, attr, default)
    return default

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
        poll_interval_seconds: float | None = None,
        fallback_scan_interval_seconds: float | None = None,
        heartbeat_interval_seconds: float = 30.0,
        batch_size: int | None = None,
        inflight: InflightLeaseRegistry | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(
            session_factory=session_factory,
            logger=logger,
            # 空转周期的心跳写事务降频(在 BaseWorker 统一实现),避免每秒一次的无意义写放大。
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )
        settings = _safe_settings()
        self.poll_interval_seconds = _resolve(
            poll_interval_seconds,
            settings,
            "queue_worker_poll_interval_seconds",
            DEFAULT_POLL_INTERVAL_SECONDS,
        )
        # 兜底扫描是无索引可用的 Pending 全表查询,不需要每秒执行一次。
        self.fallback_scan_interval_seconds = _resolve(
            fallback_scan_interval_seconds,
            settings,
            "queue_worker_fallback_scan_interval_seconds",
            DEFAULT_FALLBACK_SCAN_INTERVAL_SECONDS,
        )
        # 单轮批大小上限:此前 get_nowait() 会把队列整个抽干合并成一个 set,
        # 重启后 pending 堆积 + scheduler 每 tick 推 N 条,单轮可能是几百条,
        # 全程串行无 checkpoint,中途异常整批白干。
        self.batch_size = max(
            int(
                _resolve(
                    batch_size,
                    settings,
                    "news_signal_backlog_batch_size",
                    DEFAULT_BACKLOG_BATCH_SIZE,
                )
            ),
            1,
        )
        self.inflight = inflight if inflight is not None else analysis_inflight
        self._next_fallback_scan_at = 0.0
        # 被吞掉异常的计数回写节流(见 _maybe_flush_error_metrics)。
        self._next_error_metrics_flush_at = 0.0
        self._last_reported_error_counts: dict[str, int] = {}
        # 持续故障时的失败记账节流(BaseWorker 只对 _record_success 做了节流)。
        self._last_failure_record_at = float("-inf")

    def get_interval(self) -> float:
        return self.poll_interval_seconds

    def _record_failure(self, error: str) -> None:
        """失败记账节流。

        BaseWorker._record_success 已有 30s 心跳节流,但 _record_failure 每次失败
        都会写库;持续故障时本 worker 会以 poll_interval(默认 1s)的频率反复写
        `worker_runtime_status`。这里只节流"写库",日志仍由 run_cycle 每轮打印。
        """
        now = time.monotonic()
        if now - self._last_failure_record_at < FAILURE_RECORD_MIN_INTERVAL_SECONDS:
            return
        self._last_failure_record_at = now
        super()._record_failure(error)

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

    def _drain_queue(self) -> list[int]:
        """从内存队列取出至多 `batch_size` 个 id,超出的整块放回队列。

        此前是无上限抽干:重启后 pending 堆积时单轮可能几百条,串行处理且
        无 checkpoint,中途异常整批白干。
        """
        batch_ids: list[int] = []
        seen: set[int] = set()
        while len(batch_ids) < self.batch_size and not self._stop_event.is_set():
            try:
                news_ids = analysis_queue.get_nowait()
            except queue.Empty:
                break
            analysis_queue.task_done()

            overflow: list[int] = []
            for news_id in news_ids:
                if news_id in seen:
                    continue
                if len(batch_ids) < self.batch_size:
                    seen.add(news_id)
                    batch_ids.append(news_id)
                else:
                    overflow.append(news_id)
            if overflow:
                # 本块没吃完:剩余部分原样放回,下一轮继续(顺序无关紧要)。
                analysis_queue.put(overflow)
                break
        return batch_ids

    def do_cycle(self) -> int:
        """异步消化分析队列。"""
        self._maybe_flush_error_metrics()

        cycle_started = time.perf_counter()
        queue_depth_before = analysis_queue.qsize()
        batch_ids = self._drain_queue()
        from_fallback = False

        # 自愈兜底：如果内存队列为空，定期(而非每个轮询周期)去数据库拉取 Pending 新闻
        if not batch_ids:
            now = time.monotonic()
            if now < self._next_fallback_scan_at:
                return 0
            self._next_fallback_scan_at = now + self.fallback_scan_interval_seconds
            with self.session_factory() as session:
                pipeline = NewsSignalPipelineService(session, session_factory=self.session_factory)
                # 兜底扫描同样要避开在处理中的 id,否则崩溃恢复路径又会重复消费。
                candidates = pipeline.list_pending_news_ids(
                    limit=self.batch_size + self.inflight.active_count()
                )
                batch_ids = self.inflight.acquire(candidates, limit=self.batch_size)
                from_fallback = True

        if not batch_ids:
            return 0

        target_ids = list(batch_ids)
        # 领取租约:在 signal_status 写回之前,scheduler 不会再把这批 id 重复投递。
        self.inflight.touch(target_ids)
        self.logger.info(
            "queue worker batch claimed: count=%s from_fallback=%s queue_depth=%s inflight=%s ids=%s",
            len(target_ids),
            from_fallback,
            queue_depth_before,
            self.inflight.active_count(),
            target_ids,
        )

        event_bus = get_event_bus()
        notification_service = get_notification_service()

        pipeline_ms = 0.0
        persist_ms = 0.0
        publish_ms = 0.0
        try:
            with self.session_factory() as session:
                # 1. 执行重负载管线 (LLM 调用在写事务之外的纯内存阶段完成)
                stage_started = time.perf_counter()
                pipeline = NewsSignalPipelineService(session, session_factory=self.session_factory)
                summary = pipeline.process_news_ids(target_ids)
                pipeline_ms = (time.perf_counter() - stage_started) * 1000

                # 2. 批量加载新闻实体 (N+1 修复)
                stage_started = time.perf_counter()
                news_repo = NewsRepository(session)
                items = news_repo.get_by_ids(summary.news_ids)

                # commit 之后 ORM 实例会因 expire_on_commit=True 过期,再访问
                # item.title/summary/... 会各触发一次 SELECT refresh(N 次查询)。
                # 因此把事件与通知需要的字段全部在 commit 之前取成普通 Python 值。
                update_payloads: list[dict] = []
                notification_payloads: list[dict] = []
                for item in items:
                    payload = NewsItemSummary.model_validate(item, from_attributes=True).model_dump(mode="json")
                    payload["updated_fields"] = ["sentiment_label"]
                    update_payloads.append(payload)
                    notification_payloads.append(
                        {
                            "title": item.title,
                            "summary": item.summary,
                            "source_name": item.source_name,
                            "market": item.market,
                            "published_at": item.published_at.isoformat() if item.published_at else None,
                        }
                    )

                session.commit()
                persist_ms = (time.perf_counter() - stage_started) * 1000

                # 3. 广播已评分事件，并批量进行通知草稿入队(一次配置加载 + 一次提交)
                stage_started = time.perf_counter()
                publish_batch = getattr(event_bus, "publish_batch", None)
                if callable(publish_batch):
                    publish_batch("news.updated", update_payloads)
                else:  # 兼容只实现了 publish() 的测试替身
                    for payload in update_payloads:
                        event_bus.publish("news.updated", payload)
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
                publish_ms = (time.perf_counter() - stage_started) * 1000

            if summary.processed_count > 0:
                event_bus.publish(
                    "news.signals_processed",
                    {"news_ids": summary.news_ids, "processed_count": summary.processed_count},
                )
        finally:
            # 无论成功还是异常都释放租约:成功的条目 signal_status 已经写回不会
            # 再被选中,失败的条目下一轮可以正常重试(而不是被租约锁死 600s)。
            self.inflight.release(target_ids)

        self.logger.info(
            "queue worker cycle done: batch=%s processed=%s pipeline_ms=%.1f persist_ms=%.1f "
            "publish_ms=%.1f total_ms=%.1f queue_depth=%s inflight=%s",
            len(target_ids),
            summary.processed_count,
            pipeline_ms,
            persist_ms,
            publish_ms,
            (time.perf_counter() - cycle_started) * 1000,
            analysis_queue.qsize(),
            self.inflight.active_count(),
        )
        return summary.processed_count


DEFAULT_ORPHAN_DRAIN_INTERVAL_SECONDS = 60.0


class OrphanQueueDrainWorker(BaseWorker):
    """多进程形态下，web 进程里「无消费者的进程内队列」回收器。

    背景:`analysis_queue` 与 `takeaway_queue` 都是**进程内**的 `queue.Queue`,
    而它们的生产者留在 web 进程里:

    - `NewsIngestScheduler._drain_signal_backlog()` 每个 tick 把 pending id
      塞进 `analysis_queue`（scheduler 仍随 web 进程运行）;
    - `NewsFeedLayoutService` 在**请求线程**里把高分候选塞进 `takeaway_queue`。

    `PIPELINE_WORKERS_ENABLED=false` 时这两个队列在 web 进程内再无消费者,不回收
    就是慢性内存泄漏。真正的消费发生在独立 pipeline worker 进程里:analysis 侧走
    「Redis 事件 + 每 30s 的 DB 兜底扫描」,takeaway 侧走
    `takeaway_fallback_scan_interval_seconds` 的 DB 兜底扫描,所以在这里丢弃**不会**
    丢工作量,只是丢掉一份本进程用不上的副本。

    刻意**不**释放 `analysis_inflight` 里的租约:释放会让 scheduler 下一个 tick
    立刻重新领取并重新入队,变成 5s 一次的空转;让它按 600s 自然过期即可,租约表
    本身的规模由 pending 数量封顶。
    """

    worker_name = "orphan_queue_drainer"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        interval_seconds: float | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        settings = _safe_settings()
        self.interval_seconds = max(
            float(
                _resolve(
                    interval_seconds,
                    settings,
                    "orphan_queue_drain_interval_seconds",
                    DEFAULT_ORPHAN_DRAIN_INTERVAL_SECONDS,
                )
            ),
            1.0,
        )

    def get_interval(self) -> float:
        return self.interval_seconds

    @staticmethod
    def _drain(target: queue.Queue) -> int:
        dropped = 0
        while True:
            try:
                chunk = target.get_nowait()
            except queue.Empty:
                return dropped
            target.task_done()
            dropped += len(chunk) if isinstance(chunk, (list, set, tuple)) else 1

    def do_cycle(self) -> int:
        # 延迟导入:避免 queue_worker -> news_takeaway 的模块级依赖（news_takeaway
        # 只被 feed layout 这条请求侧链路需要）。
        from app.services.news_takeaway import takeaway_queue

        dropped_analysis = self._drain(analysis_queue)
        dropped_takeaway = self._drain(takeaway_queue)
        total = dropped_analysis + dropped_takeaway
        if total:
            self.logger.info(
                "orphan queue drained (pipeline workers run out-of-process): "
                "analysis_ids=%s takeaway_ids=%s",
                dropped_analysis,
                dropped_takeaway,
            )
        return total
