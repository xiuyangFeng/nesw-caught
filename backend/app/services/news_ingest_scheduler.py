from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.news_ingestion import NewsIngestionService, SourceDefinition, load_sources
from app.services.news_signal_pipeline import NewsSignalPipelineService
from app.workers.base_worker import BaseWorker
from app.workers.queue_worker import analysis_inflight, analysis_queue

DEFAULT_TICK_SECONDS = 5.0
DEFAULT_MAX_BACKOFF_MULTIPLIER = 8
DEFAULT_EMPTY_CIRCUIT_THRESHOLD = 3
SIGNAL_BACKLOG_BATCH_SIZE = 50
DEFAULT_STARTUP_JITTER_SECONDS = 8.0


def _safe_settings():
    try:
        return get_settings()
    except Exception:  # pragma: no cover - 配置不可用是极端情况
        return None


SUCCESS_STATUSES = frozenset({"ok", "not_modified"})
SOFT_STATUSES = frozenset({"empty"})
FAILURE_STATUSES = frozenset({"http_error", "parse_error", "error"})


class NewsIngestScheduler(BaseWorker):
    """常驻新闻抓取调度器。

    - 每个源按自身 cadence_seconds 独立到期,抓取由 NewsIngestionService 并发执行、串行落库;
    - 硬失败(http/parse_error)按指数退避降频:delay = cadence * min(2^failures, max_multiplier);
    - 连续 empty 达到阈值后进入低频探测,不计入硬失败 streak;
    - 每轮把信号 pipeline 积压转交给 BackgroundQueueWorker(单入口,避免重复消费/重复 LLM);
      投递前经过进程内 in-flight 租约过滤,避免"批次耗时 > tick"时同一批 id 跨轮反复投递。
    """

    worker_name = "news_ingest_scheduler"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        tick_seconds: float = DEFAULT_TICK_SECONDS,
        max_backoff_multiplier: int = DEFAULT_MAX_BACKOFF_MULTIPLIER,
        empty_circuit_threshold: int = DEFAULT_EMPTY_CIRCUIT_THRESHOLD,
        sources_loader: Callable[[], list[SourceDefinition]] = load_sources,
        backlog_batch_size: int | None = None,
        startup_jitter_seconds: float | None = None,
        inflight=None,
        logger: logging.Logger | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.tick_seconds = max(tick_seconds, 0.1)
        self.max_backoff_multiplier = max(max_backoff_multiplier, 1)
        self.empty_circuit_threshold = max(empty_circuit_threshold, 1)
        self.sources_loader = sources_loader
        self.clock = clock
        settings = _safe_settings()
        self.backlog_batch_size = max(
            int(
                backlog_batch_size
                if backlog_batch_size is not None
                else getattr(settings, "news_signal_backlog_batch_size", SIGNAL_BACKLOG_BATCH_SIZE)
            ),
            1,
        )
        self.startup_jitter_seconds = max(
            float(
                startup_jitter_seconds
                if startup_jitter_seconds is not None
                else getattr(settings, "news_scheduler_startup_jitter_seconds", DEFAULT_STARTUP_JITTER_SECONDS)
            ),
            0.0,
        )
        # 与 BackgroundQueueWorker 共享的 in-flight 租约表(模块级单例)。
        self.inflight = inflight if inflight is not None else analysis_inflight
        self._rng = random.Random()
        self._next_due_at: dict[str, float] = {}
        self._failure_streak: dict[str, int] = {}
        self._empty_streak: dict[str, int] = {}

    def get_interval(self) -> float:
        return self.tick_seconds

    # -------------------------------------------------------------- 启动抖动

    def apply_startup_jitter(self) -> dict[str, float]:
        """给各源的首次 due 时间加随机抖动,打散进程重启后的惊群。

        `_next_due_at` 全在进程内存里,重启后所有源的 next_due 都是 0.0 → 全部源
        在第一个 tick 同时到期(16 个源挤 8 个 fetch worker,退避状态也一并清零)。
        这里在真实拉起(start/run_forever)时把首轮 due 打散到 [0, jitter) 区间。

        刻意只在 start()/run_forever() 时施加:直接调用 run_cycle() 的脚本与测试
        保持"首轮立即全量抓取"的确定性行为。
        """
        if self.startup_jitter_seconds <= 0:
            return dict(self._next_due_at)
        now = self.clock()
        try:
            sources = self.sources_loader()
        except Exception:
            self.logger.exception("failed to load sources for startup jitter")
            return dict(self._next_due_at)
        for source in sources:
            if source.name in self._next_due_at:
                continue
            self._next_due_at[source.name] = now + self._rng.uniform(0.0, self.startup_jitter_seconds)
        self.logger.info(
            "scheduler startup jitter applied: sources=%s window=%.1fs",
            len(self._next_due_at),
            self.startup_jitter_seconds,
        )
        return dict(self._next_due_at)

    def start(self) -> None:
        self.apply_startup_jitter()
        super().start()

    def run_forever(self) -> None:
        self.apply_startup_jitter()
        super().run_forever()

    # ------------------------------------------------------------------ core

    def due_sources(self) -> list[SourceDefinition]:
        now = self.clock()
        return [
            source
            for source in self.sources_loader()
            if not source.disabled and self._next_due_at.get(source.name, 0.0) <= now
        ]

    def backoff_delay_seconds(self, source: SourceDefinition) -> float:
        failures = self._failure_streak.get(source.name, 0)
        empties = self._empty_streak.get(source.name, 0)
        if failures > 0:
            multiplier = min(2**failures, self.max_backoff_multiplier)
        elif empties >= self.empty_circuit_threshold:
            # 低频探测:阈值后从 2x 起算
            probe_level = empties - self.empty_circuit_threshold + 1
            multiplier = min(2**probe_level, self.max_backoff_multiplier)
        else:
            multiplier = 1
        return float(source.cadence_seconds * multiplier)

    def do_cycle(self) -> int:
        """执行一轮调度,返回本轮插入的新闻数量。"""
        due = self.due_sources()
        self._drain_signal_backlog()

        if not due:
            return 0

        cycle_started = time.perf_counter()
        try:
            with self.session_factory() as session:
                summary = NewsIngestionService(session).refresh_all(sources=due)
        except Exception as exc:  # 整轮失败(如数据库不可用):全部源退避一个 tick,不更新 due 表。
            self.logger.exception("news refresh cycle failed")
            raise exc
        self.logger.info(
            "scheduler refresh cycle done: due_sources=%s inserted=%s elapsed_ms=%.1f queue_depth=%s inflight=%s",
            len(due),
            summary.inserted_count,
            (time.perf_counter() - cycle_started) * 1000,
            analysis_queue.qsize(),
            self.inflight.active_count(),
        )

        now = self.clock()
        results_by_name = {result.source_name: result for result in summary.results}
        for source in due:
            result = results_by_name.get(source.name)
            status = result.status if result is not None else "http_error"
            if status in SUCCESS_STATUSES:
                self._failure_streak[source.name] = 0
                self._empty_streak[source.name] = 0
            elif status in SOFT_STATUSES:
                self._failure_streak[source.name] = 0
                self._empty_streak[source.name] = self._empty_streak.get(source.name, 0) + 1
                self.logger.info(
                    "source %s empty batch (streak=%s)",
                    source.name,
                    self._empty_streak[source.name],
                )
            else:
                self._failure_streak[source.name] = self._failure_streak.get(source.name, 0) + 1
                self._empty_streak[source.name] = 0
                error = result.error if result is not None else "missing result"
                self.logger.warning(
                    "source %s failed (streak=%s status=%s): %s",
                    source.name,
                    self._failure_streak[source.name],
                    status,
                    error,
                )
            self._next_due_at[source.name] = now + self.backoff_delay_seconds(source)

        return summary.inserted_count

    def _drain_signal_backlog(self) -> int:
        """把历史积压的未分类新闻投给 BackgroundQueueWorker 的分析队列。

        pending 处理只保留 queue_worker 单入口：此处不做爬正文/LLM，
        避免与 queue_worker 并行重复消费同一批 pending（重复爬取 + 双倍 token），
        也避免在调度线程内持写锁跑秒级 LLM 调用。

        关键修复(P0):`signal_status` 要等管线阶段 2b 提交后才变成 "processed",
        而本方法每个 tick(默认 5s)都会跑一次;批次耗时必然 > tick,于是同一批 id
        会被反复投递、下一轮整批重跑(重复爬正文 + 双倍 LLM token)。这里用
        in-flight 租约把"已领取、尚未回写状态"的 id 过滤掉;租约过期(worker 崩溃)
        后才允许重投,保证不会永久漏处理。
        """
        try:
            inflight_count = self.inflight.active_count()
            with self.session_factory() as session:
                pipeline = NewsSignalPipelineService(session)
                # 多取 inflight 条:否则最近的 N 条全在处理中时会看不到更旧的积压。
                pending_ids = pipeline.list_pending_news_ids(
                    limit=self.backlog_batch_size + inflight_count
                )
            if not pending_ids:
                return 0
            claimed = self.inflight.acquire(list(pending_ids), limit=self.backlog_batch_size)
            skipped = len(pending_ids) - len(claimed)
            if not claimed:
                if skipped:
                    self.logger.debug(
                        "signal backlog fully in-flight: skipped=%s inflight=%s", skipped, inflight_count
                    )
                return 0
            analysis_queue.put(claimed)
            self.logger.info(
                "signal backlog enqueued: count=%s skipped_inflight=%s queue_depth=%s",
                len(claimed),
                skipped,
                analysis_queue.qsize(),
            )
            return len(claimed)
        except Exception:
            self.logger.exception("signal backlog enqueue failed")
            return 0
