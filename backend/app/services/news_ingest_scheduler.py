from __future__ import annotations

import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.services.news_ingestion import NewsIngestionService, SourceDefinition, load_sources
from app.services.news_signal_pipeline import NewsSignalPipelineService
from app.workers.base_worker import BaseWorker

DEFAULT_TICK_SECONDS = 5.0
DEFAULT_MAX_BACKOFF_MULTIPLIER = 8
SIGNAL_BACKLOG_BATCH_SIZE = 50


class NewsIngestScheduler(BaseWorker):
    """常驻新闻抓取调度器。

    - 每个源按自身 cadence_seconds 独立到期,抓取由 NewsIngestionService 并发执行、串行落库;
    - 连续失败的源按指数退避降频:delay = cadence * min(2^failures, max_multiplier);
    - 每轮顺带消化信号 pipeline 积压,修复“有新新闻时积压被饿死”的旧逻辑。
    """

    worker_name = "news_ingest_scheduler"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        tick_seconds: float = DEFAULT_TICK_SECONDS,
        max_backoff_multiplier: int = DEFAULT_MAX_BACKOFF_MULTIPLIER,
        sources_loader: Callable[[], list[SourceDefinition]] = load_sources,
        logger: logging.Logger | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(session_factory=session_factory, logger=logger)
        self.tick_seconds = max(tick_seconds, 0.1)
        self.max_backoff_multiplier = max(max_backoff_multiplier, 1)
        self.sources_loader = sources_loader
        self.clock = clock
        self._next_due_at: dict[str, float] = {}
        self._failure_streak: dict[str, int] = {}

    def get_interval(self) -> float:
        return self.tick_seconds

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
        multiplier = min(2**failures, self.max_backoff_multiplier) if failures > 0 else 1
        return float(source.cadence_seconds * multiplier)

    def do_cycle(self) -> int:
        """执行一轮调度,返回本轮插入的新闻数量。"""
        due = self.due_sources()
        self._drain_signal_backlog()

        if not due:
            return 0

        try:
            with self.session_factory() as session:
                summary = NewsIngestionService(session).refresh_all(sources=due)
        except Exception as exc:  # 整轮失败(如数据库不可用):全部源退避一个 tick,不更新 due 表。
            self.logger.exception("news refresh cycle failed")
            raise exc

        now = self.clock()
        results_by_name = {result.source_name: result for result in summary.results}
        for source in due:
            result = results_by_name.get(source.name)
            if result is not None and result.status == "ok":
                self._failure_streak[source.name] = 0
            else:
                self._failure_streak[source.name] = self._failure_streak.get(source.name, 0) + 1
                error = result.error if result is not None else "missing result"
                self.logger.warning("source %s failed (streak=%s): %s", source.name, self._failure_streak[source.name], error)
            self._next_due_at[source.name] = now + self.backoff_delay_seconds(source)

        return summary.inserted_count

    def _drain_signal_backlog(self) -> int:
        """消化历史积压的未分类新闻(刚插入的新闻由事件订阅方处理)。"""
        try:
            with self.session_factory() as session:
                pipeline = NewsSignalPipelineService(session)
                pending_ids = pipeline.list_pending_news_ids(limit=SIGNAL_BACKLOG_BATCH_SIZE)
                if not pending_ids:
                    return 0
                pipeline.process_news_ids(pending_ids)
                session.commit()
                return len(pending_ids)
        except Exception:
            self.logger.exception("signal backlog processing failed")
            return 0
