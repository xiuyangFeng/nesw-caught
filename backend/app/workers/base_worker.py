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
        heartbeat_interval_seconds: float = 30.0,
    ) -> None:
        self.session_factory = session_factory
        self.logger = logger or logging.getLogger(self.__class__.__module__)
        # 空闲周期(processed_count==0)的心跳写库节流:距上次心跳不足该间隔时跳过,
        # 避免高频轮询 worker 每秒一次的 get+update 写放大。
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self._last_heartbeat_at = float("-inf")
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
            now = time.monotonic()
            if count == 0 and now - self._last_heartbeat_at < self.heartbeat_interval_seconds:
                return
            # 无论本次写库成败都先刷新心跳时间戳:故障期同样节流,避免每周期重试写放大。
            self._last_heartbeat_at = now
            with self.session_factory() as session:
                WorkerRuntimeStatusRepository(session).record_success(
                    worker_name=self.worker_name,
                    quotes_count=count,
                )
                # 非请求上下文：repository 只 flush，提交边界在这里。
                session.commit()
        except Exception:
            # 兜底范围刻意保持宽泛(而非收窄为 SQLAlchemyError):调用方可能传入不完全
            # 模拟真实 SQLAlchemy Session 的测试替身/未来实现(例如缺少 .scalar()
            # 方法),此时会抛出 AttributeError/TypeError 而非 SQLAlchemyError。
            # 本方法的契约是"记账失败绝不能让 worker 主循环崩溃或改变 run_cycle()
            # 的返回值语义",因此保留 Exception 兜底,仅确保日志带 worker 名称上下文。
            self.logger.exception("Failed to record worker '%s' success status", self.worker_name)

    def _record_failure(self, error: str) -> None:
        try:
            with self.session_factory() as session:
                WorkerRuntimeStatusRepository(session).record_failure(
                    worker_name=self.worker_name,
                    error=error,
                )
                # 非请求上下文：repository 只 flush，提交边界在这里。
                session.commit()
        except Exception:
            # 同上:刻意保持 Exception 兜底,避免因调用方 session_factory 传入的
            # 测试替身/异常 Session 实现类型不可控,导致记账失败反过来让
            # run_cycle() 抛出而破坏"从不崩溃"的对外契约。
            self.logger.exception("Failed to record worker '%s' failure status", self.worker_name)
