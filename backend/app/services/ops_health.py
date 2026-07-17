"""统一系统健康看板的按需聚合服务。

把散落在各处的可观测数据（worker 运行时状态、新闻源 / X 源健康、近 24h LLM 用量、
事件层状态、SQLite 文件体积）在一次请求里聚合成 :class:`OpsHealthResponse`，
并基于模块级阈值常量产出结构化 ``alerts``（每条告警同时 ``logger.warning``）。

设计约束（与本特性任务对齐）：
- 只读聚合，不新增数据库表 / 迁移；
- 阈值用模块常量，不改 ``config.py``；
- 不主动推送（不碰 notification_service / feishu），只在响应里暴露 + 记 WARNING 日志，
  主动推送留作扩展点。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.llm_token_usage import LLMTokenUsage
from app.models.source_health import SourceHealth
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.models.x_source_health import XSourceHealth
from app.schemas.ops import (
    OpsAlert,
    OpsDatabaseView,
    OpsEventBusView,
    OpsHealthResponse,
    OpsLlmModelUsageView,
    OpsLlmUsageView,
    OpsSourceView,
    OpsWorkerView,
    OpsXSourceView,
)
from app.services.event_bus import get_event_bus

logger = logging.getLogger(__name__)

# --- 告警阈值（模块常量，刻意不进 config.py，避免与其它代理的改动冲突）---------
# 源（新闻源 / X 源）连续失败达到该次数即告警。
SOURCE_CONSECUTIVE_FAILURE_THRESHOLD = 5
# worker 距最近心跳超过该秒数视为心跳超时（后台线程静默失败的主要信号）。
WORKER_HEARTBEAT_TIMEOUT_SECONDS = 300
# SQLite 文件体积告警阈值（MB）：超过 WARNING 记 warning，超过 CRITICAL 记 critical。
DB_SIZE_WARNING_MB = 500.0
DB_SIZE_CRITICAL_MB = 1024.0
# LLM 用量统计窗口（小时）。
LLM_USAGE_WINDOW_HOURS = 24


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime | None) -> datetime | None:
    """把 DB 读回的（可能是 naive 的）时间统一成带 UTC 时区。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _success_rate(total_fetches: int, total_failures: int) -> float | None:
    """成功率 = (总抓取 - 总失败) / 总抓取，返回 0..1 小数；从未抓取返回 None。"""
    if total_fetches <= 0:
        return None
    rate = (total_fetches - total_failures) / total_fetches
    # 容错：数据异常时夹逼到 [0, 1]。
    rate = max(0.0, min(1.0, rate))
    return round(rate, 4)


def _collect_workers(session: Session, now: datetime) -> list[OpsWorkerView]:
    rows = list(
        session.scalars(select(WorkerRuntimeStatus).order_by(WorkerRuntimeStatus.worker_name.asc()))
    )
    workers: list[OpsWorkerView] = []
    for row in rows:
        heartbeat = _ensure_utc(row.last_heartbeat_at)
        age = (now - heartbeat).total_seconds() if heartbeat is not None else None
        workers.append(
            OpsWorkerView(
                name=row.worker_name,
                status=row.status,
                last_heartbeat_at=row.last_heartbeat_at,
                last_success_at=row.last_success_at,
                last_failure_at=row.last_failure_at,
                last_error=row.last_error,
                cycle_count=row.cycle_count,
                success_count=row.success_count,
                failure_count=row.failure_count,
                last_quotes_count=row.last_quotes_count,
                heartbeat_age_seconds=round(age, 1) if age is not None else None,
            )
        )
    return workers


def _collect_sources(session: Session) -> list[OpsSourceView]:
    rows = list(
        session.scalars(
            select(SourceHealth).order_by(SourceHealth.source_name.asc(), SourceHealth.market.asc())
        )
    )
    return [
        OpsSourceView(
            source_name=row.source_name,
            market=row.market,
            source_type=row.source_type,
            last_success_at=row.last_success_at,
            last_failure_at=row.last_failure_at,
            consecutive_failures=row.consecutive_failures,
            total_fetches=row.total_fetches,
            total_failures=row.total_failures,
            success_rate=_success_rate(row.total_fetches, row.total_failures),
            avg_latency_ms=row.avg_latency_ms,
            is_disabled=row.is_disabled,
            last_status=row.last_status,
            last_error=row.last_error,
            last_http_status=row.last_http_status,
            last_fetched_count=row.last_fetched_count or 0,
            last_inserted_count=row.last_inserted_count or 0,
            consecutive_empty_batches=row.consecutive_empty_batches or 0,
        )
        for row in rows
    ]


def _collect_x_sources(session: Session) -> list[OpsXSourceView]:
    rows = list(
        session.scalars(select(XSourceHealth).order_by(XSourceHealth.provider_name.asc()))
    )
    return [
        OpsXSourceView(
            provider_name=row.provider_name,
            last_success_at=row.last_success_at,
            last_failure_at=row.last_failure_at,
            consecutive_failures=row.consecutive_failures,
            total_fetches=row.total_fetches,
            total_failures=row.total_failures,
            success_rate=_success_rate(row.total_fetches, row.total_failures),
            avg_latency_ms=row.avg_latency_ms,
            last_error=row.last_error,
        )
        for row in rows
    ]


def _collect_llm_usage(session: Session, now: datetime) -> OpsLlmUsageView:
    window_start = now - timedelta(hours=LLM_USAGE_WINDOW_HOURS)

    per_model_stmt = (
        select(
            LLMTokenUsage.model_name,
            func.count(LLMTokenUsage.id).label("call_count"),
            func.sum(LLMTokenUsage.prompt_tokens).label("prompt"),
            func.sum(LLMTokenUsage.completion_tokens).label("completion"),
            func.sum(LLMTokenUsage.total_tokens).label("total"),
        )
        .where(LLMTokenUsage.created_at >= window_start)
        .group_by(LLMTokenUsage.model_name)
        .order_by(func.sum(LLMTokenUsage.total_tokens).desc())
    )

    models: list[OpsLlmModelUsageView] = []
    total_calls = 0
    total_prompt = 0
    total_completion = 0
    total_tokens = 0
    for row in session.execute(per_model_stmt):
        call_count = int(row.call_count or 0)
        prompt = int(row.prompt or 0)
        completion = int(row.completion or 0)
        total = int(row.total or 0)
        total_calls += call_count
        total_prompt += prompt
        total_completion += completion
        total_tokens += total
        models.append(
            OpsLlmModelUsageView(
                model_name=row.model_name,
                call_count=call_count,
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
            )
        )

    return OpsLlmUsageView(
        window_hours=LLM_USAGE_WINDOW_HOURS,
        call_count=total_calls,
        prompt_tokens=total_prompt,
        completion_tokens=total_completion,
        total_tokens=total_tokens,
        models=models,
    )


def _collect_event_bus() -> OpsEventBusView:
    status = get_event_bus().get_status()
    return OpsEventBusView(
        backend=status.backend,
        status=status.status,
        redis_enabled=status.redis_enabled,
        last_published_at=status.last_published_at,
        last_event_name=status.last_event_name,
        last_error=status.last_error,
    )


def _collect_database() -> OpsDatabaseView:
    """对 ``database_url`` 指向的 SQLite 文件取体积；非 SQLite / 内存库优雅降级。"""
    settings = get_settings()
    db_path: str | None = None
    try:
        db_path = make_url(settings.database_url).database
    except Exception:  # pragma: no cover - URL 解析异常兜底
        db_path = None

    size_bytes = 0
    exists = False
    if db_path:
        from pathlib import Path

        path_obj = Path(db_path)
        if path_obj.exists() and path_obj.is_file():
            exists = True
            # WAL 模式下主库文件可能很小，真实落盘数据在 -wal 里；把主库 + WAL
            # 旁路文件（-wal / -shm）一并计入，得到贴近实际的磁盘占用。
            for candidate in (path_obj, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
                try:
                    if candidate.exists() and candidate.is_file():
                        size_bytes += candidate.stat().st_size
                except OSError:  # pragma: no cover - 罕见 IO 异常兜底
                    continue

    return OpsDatabaseView(
        path=db_path,
        exists=exists,
        size_bytes=size_bytes,
        size_mb=round(size_bytes / (1024 * 1024), 2),
    )


def _evaluate_alerts(
    *,
    workers: list[OpsWorkerView],
    sources: list[OpsSourceView],
    x_sources: list[OpsXSourceView],
    event_bus: OpsEventBusView,
    database: OpsDatabaseView,
) -> list[OpsAlert]:
    """基于阈值把聚合结果转成告警列表；每条告警同时 logger.warning。"""
    alerts: list[OpsAlert] = []

    def _add(level: str, code: str, subject: str, message: str) -> None:
        alerts.append(OpsAlert(level=level, code=code, subject=subject, message=message))
        logger.warning("ops-health alert [%s] %s (%s): %s", level, code, subject, message)

    # 1) worker 心跳超时 / 降级。
    for worker in workers:
        age = worker.heartbeat_age_seconds
        if age is not None and age > WORKER_HEARTBEAT_TIMEOUT_SECONDS:
            _add(
                "warning",
                "worker.heartbeat_timeout",
                worker.name,
                f"worker {worker.name} 心跳已停滞 {int(age)}s，超过阈值 {WORKER_HEARTBEAT_TIMEOUT_SECONDS}s",
            )
        if worker.status == "degraded":
            detail = f"，最近错误：{worker.last_error}" if worker.last_error else ""
            _add(
                "warning",
                "worker.degraded",
                worker.name,
                f"worker {worker.name} 处于 degraded 状态{detail}",
            )

    # 2) 新闻源连续失败 / 被禁用。
    for source in sources:
        subject = f"{source.source_name}@{source.market}"
        if source.consecutive_failures >= SOURCE_CONSECUTIVE_FAILURE_THRESHOLD:
            _add(
                "warning",
                "source.consecutive_failures",
                subject,
                f"新闻源 {subject} 已连续失败 {source.consecutive_failures} 次"
                f"（阈值 {SOURCE_CONSECUTIVE_FAILURE_THRESHOLD}）",
            )
        if source.is_disabled:
            _add(
                "warning",
                "source.disabled",
                subject,
                f"新闻源 {subject} 已被自动禁用",
            )

    # 3) X 源连续失败。
    for x_source in x_sources:
        if x_source.consecutive_failures >= SOURCE_CONSECUTIVE_FAILURE_THRESHOLD:
            _add(
                "warning",
                "x_source.consecutive_failures",
                x_source.provider_name,
                f"X 源 {x_source.provider_name} 已连续失败 {x_source.consecutive_failures} 次"
                f"（阈值 {SOURCE_CONSECUTIVE_FAILURE_THRESHOLD}）",
            )

    # 4) 事件层降级。
    if event_bus.status == "degraded":
        detail = f"，最近错误：{event_bus.last_error}" if event_bus.last_error else ""
        _add(
            "warning",
            "event_bus.degraded",
            "event_bus",
            f"事件层（backend={event_bus.backend}）处于 degraded 状态{detail}",
        )

    # 5) SQLite 体积异常。
    if database.size_mb > DB_SIZE_CRITICAL_MB:
        _add(
            "critical",
            "database.size",
            "database",
            f"数据库体积 {database.size_mb}MB 超过临界阈值 {DB_SIZE_CRITICAL_MB}MB",
        )
    elif database.size_mb > DB_SIZE_WARNING_MB:
        _add(
            "warning",
            "database.size",
            "database",
            f"数据库体积 {database.size_mb}MB 超过告警阈值 {DB_SIZE_WARNING_MB}MB",
        )

    return alerts


def _overall_status(alerts: list[OpsAlert]) -> str:
    if any(alert.level == "critical" for alert in alerts):
        return "critical"
    if any(alert.level == "warning" for alert in alerts):
        return "warning"
    return "ok"


def build_ops_health(session: Session) -> OpsHealthResponse:
    """一次性聚合系统健康快照并产出告警列表。

    对无数据（各表为空）的场景不崩：返回空列表 + ``ok`` 状态。
    """
    now = _utc_now()

    workers = _collect_workers(session, now)
    sources = _collect_sources(session)
    x_sources = _collect_x_sources(session)
    llm_usage = _collect_llm_usage(session, now)
    event_bus = _collect_event_bus()
    database = _collect_database()

    alerts = _evaluate_alerts(
        workers=workers,
        sources=sources,
        x_sources=x_sources,
        event_bus=event_bus,
        database=database,
    )

    return OpsHealthResponse(
        generated_at=now,
        overall_status=_overall_status(alerts),
        alerts=alerts,
        workers=workers,
        sources=sources,
        x_sources=x_sources,
        llm_usage=llm_usage,
        event_bus=event_bus,
        database=database,
    )
