from __future__ import annotations

import logging
import time
from collections.abc import Callable
from threading import Event, Thread
from typing import Any

from sqlalchemy.orm import Session
from app.repositories.worker_runtime_status_repository import WorkerRuntimeStatusRepository


class BaseWorker:
    """抽象后台 Worker 基类。

    - 统一 start() / stop() 生命周期控制；
    - 使用 Event.wait(interval) 代替 time.sleep() 以实现即时中断退场；
    - 统一心跳汇报与异常恢复兜底。
    """

    worker_name = "base_worker"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        logger: logging.Logger | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.logger = logger or logging.getLogger(self.__class__.__module__)
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._is_running = False

    def start(self) -> None:
        """启动后台服务线程。"""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, name=self.worker_name, daemon=True)
        self._thread.start()
        self.logger.info("Worker '%s' started", self.worker_name)

    def stop(self, timeout: float = 2.0) -> None:
        """停止后台服务线程。"""
        if not self._is_running:
            return
        self._is_running = False
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self.logger.info("Worker '%s' stopped", self.worker_name)

    def run_forever(self) -> None:
        """同步运行（用于单独进程拉起）。"""
        self._is_running = True
        self._stop_event.clear()
        self._run_loop()

    def get_interval(self) -> float:
        """返回每次循环等待的时间。由子类覆盖。"""
        return 5.0

    def run_cycle(self) -> int:
        """执行一个周期的动作，包含异常捕获与状态记账。"""
        try:
            processed_count = self.do_cycle()
            self._record_success(processed_count)
            return processed_count
        except Exception as exc:
            self.logger.exception("Worker '%s' cycle failed: %s", self.worker_name, exc)
            self._record_failure(str(exc))
            return 0

    def do_cycle(self) -> int:
        """执行一个周期的动作。由子类覆盖并实现，返回处理的数据量以供统计。"""
        raise NotImplementedError()

    def _run_loop(self) -> None:
        while self._is_running and not self._stop_event.is_set():
            started = time.perf_counter()
            self.run_cycle()
            elapsed = time.perf_counter() - started
            interval = max(self.get_interval() - elapsed, 0.1)
            self._stop_event.wait(interval)

    def _record_success(self, processed_count: Any = 0) -> None:
        try:
            count = processed_count if isinstance(processed_count, int) else 0
            with self.session_factory() as session:
                WorkerRuntimeStatusRepository(session).record_success(
                    worker_name=self.worker_name,
                    quotes_count=count,
                )
        except Exception:
            self.logger.exception("Failed to record worker '%s' success status", self.worker_name)

    def _record_failure(self, error: str) -> None:
        try:
            with self.session_factory() as session:
                WorkerRuntimeStatusRepository(session).record_failure(
                    worker_name=self.worker_name,
                    error=error,
                )
        except Exception:
            self.logger.exception("Failed to record worker '%s' failure status", self.worker_name)
