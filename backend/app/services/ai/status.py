"""AI 漏斗状态：是否在线（决定提醒走 AI 还是关键词）与状态卡数据。"""

from __future__ import annotations

import threading
import time as monotonic_time
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.llm_token_usage import LLMTokenUsage
from app.models.news_ai import STATUS_ERROR, STATUS_OK, NewsAiAnalysis, NewsAiScreen, NewsImpact
from app.models.worker_runtime_status import WorkerRuntimeStatus
from app.services.ai.llm_json import get_explicit_default_config
from app.services.llm_cost import budget_status, compute_cost_usd, load_pricing

FUNNEL_WORKER_NAME = "ai_funnel"
FUNNEL_OPERATIONS = ("ai_screen", "ai_impact", "sector_infer")
HEARTBEAT_FRESH_SECONDS = 600
_STATUS_TZ = ZoneInfo("Asia/Shanghai")
_CACHE_TTL_SECONDS = 30.0

REASON_DISABLED = "disabled"
REASON_NO_MODEL = "no_default_model"
REASON_OVER_BUDGET = "over_budget"
REASON_WORKER_DOWN = "worker_not_running"
REASON_QUOTA = "quota_exhausted"
REASON_BUDGET_UNPRICED = "budget_unpriced"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def spend_blocked_reason(session: Session, now: datetime | None = None) -> str | None:
    """花费闸：设了预算却没填单价（费用算不出、预算形同虚设），或本月已达预算。"""
    config = get_explicit_default_config(session)
    if (
        config is not None
        and config.monthly_budget_usd is not None
        and config.input_price_per_1m is None
        and config.output_price_per_1m is None
    ):
        return REASON_BUDGET_UNPRICED
    if budget_status(session, now or _utc_now()).over_budget:
        return REASON_OVER_BUDGET
    return None


def inactive_reason(session: Session, now: datetime | None = None, *, check_worker: bool = True) -> str | None:
    """漏斗不在线的原因；在线返回 None。"""
    now = now or _utc_now()
    settings = get_settings()
    if not settings.ai_funnel_enabled:
        return REASON_DISABLED
    if get_explicit_default_config(session) is None:
        return REASON_NO_MODEL
    blocked = spend_blocked_reason(session, now)
    if blocked is not None:
        return blocked
    analyzed_today = int(
        session.scalar(
            select(func.count())
            .select_from(NewsAiAnalysis)
            .where(NewsAiAnalysis.analyzed_at >= _local_day_start(now))
        )
        or 0
    )
    if analyzed_today >= settings.ai_impact_daily_limit:
        return REASON_QUOTA
    if check_worker:
        # 看最近一次"成功"周期而不是心跳：周期持续报错时心跳照样刷新。
        last_success = session.scalar(
            select(WorkerRuntimeStatus.last_success_at).where(WorkerRuntimeStatus.worker_name == FUNNEL_WORKER_NAME)
        )
        last_success = _as_utc(last_success)
        if last_success is None or now - last_success > timedelta(seconds=HEARTBEAT_FRESH_SECONDS):
            return REASON_WORKER_DOWN
    return None


class AiModeChecker:
    """提醒服务用的"AI 是否在线"判定，带 30 秒缓存（每批新闻都会调用）。"""

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal, ttl_seconds: float = _CACHE_TTL_SECONDS):
        self._session_factory = session_factory
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._cached: tuple[float, bool] | None = None

    def __call__(self) -> bool:
        now = monotonic_time.monotonic()
        with self._lock:
            if self._cached is not None and now - self._cached[0] < self._ttl:
                return self._cached[1]
        with self._session_factory() as session:
            active = inactive_reason(session) is None
        with self._lock:
            self._cached = (now, active)
        return active


def _local_day_start(now: datetime) -> datetime:
    local_day = now.astimezone(_STATUS_TZ).date()
    return datetime.combine(local_day, time.min, tzinfo=_STATUS_TZ).astimezone(UTC)


def funnel_status(session: Session, now: datetime | None = None) -> dict[str, Any]:
    now = now or _utc_now()
    settings = get_settings()
    config = get_explicit_default_config(session)
    day_start = _local_day_start(now)
    pricing = load_pricing(session)

    def count(model, *conditions) -> int:
        return int(session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)

    usage_rows = session.execute(
        select(
            LLMTokenUsage.operation_type,
            LLMTokenUsage.model_name,
            func.sum(LLMTokenUsage.prompt_tokens),
            func.sum(LLMTokenUsage.completion_tokens),
            func.count(LLMTokenUsage.id),
        )
        .where(LLMTokenUsage.created_at >= day_start, LLMTokenUsage.operation_type.in_(FUNNEL_OPERATIONS))
        .group_by(LLMTokenUsage.operation_type, LLMTokenUsage.model_name)
    ).all()
    usage: dict[str, dict[str, Any]] = {
        op: {"operation_type": op, "calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": None}
        for op in FUNNEL_OPERATIONS
    }
    for operation, model_name, prompt, completion, calls in usage_rows:
        entry = usage[operation]
        entry["calls"] += int(calls or 0)
        entry["prompt_tokens"] += int(prompt or 0)
        entry["completion_tokens"] += int(completion or 0)
        cost = compute_cost_usd(int(prompt or 0), int(completion or 0), *pricing.get(model_name, (None, None)))
        if cost is not None:
            entry["cost_usd"] = (entry["cost_usd"] or 0.0) + cost
    today_costs = [entry["cost_usd"] for entry in usage.values() if entry["cost_usd"] is not None]

    last_error = None
    for model, time_column in ((NewsAiAnalysis, NewsAiAnalysis.analyzed_at), (NewsAiScreen, NewsAiScreen.screened_at)):
        row = session.execute(
            select(model.error, time_column).where(model.status == STATUS_ERROR).order_by(time_column.desc()).limit(1)
        ).first()
        if row is not None and (last_error is None or _as_utc(row[1]) > _as_utc(last_error["at"])):
            last_error = {"message": row[0], "at": _as_utc(row[1])}

    budget = budget_status(session, now, pricing=pricing)
    return {
        "enabled": settings.ai_funnel_enabled,
        "active": inactive_reason(session, now) is None,
        "inactive_reason": inactive_reason(session, now),
        "model_name": config.model_name if config else None,
        "model_display_name": (config.display_name or config.provider_name) if config else None,
        "today": {
            "screened": count(NewsAiScreen, NewsAiScreen.screened_at >= day_start, NewsAiScreen.status == STATUS_OK),
            "screen_errors": count(
                NewsAiScreen, NewsAiScreen.screened_at >= day_start, NewsAiScreen.status == STATUS_ERROR
            ),
            "analyzed": count(
                NewsAiAnalysis, NewsAiAnalysis.analyzed_at >= day_start, NewsAiAnalysis.status == STATUS_OK
            ),
            "analysis_errors": count(
                NewsAiAnalysis, NewsAiAnalysis.analyzed_at >= day_start, NewsAiAnalysis.status == STATUS_ERROR
            ),
            "impacts": count(NewsImpact, NewsImpact.created_at >= day_start),
            "analysis_daily_limit": settings.ai_impact_daily_limit,
            "cost_usd": sum(today_costs) if today_costs else None,
        },
        "usage": list(usage.values()),
        "month_cost_usd": budget.month_cost_usd,
        "monthly_budget_usd": budget.monthly_budget_usd,
        "over_budget": budget.over_budget,
        "last_error": last_error,
    }
