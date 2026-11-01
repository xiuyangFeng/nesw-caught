"""AI 漏斗 worker（聚焦改造 P3）：每个周期 板块推断 → L1 粗筛 → L2 精读 → 提醒。

只有在"模型设置"里明确设了默认模型、漏斗开关打开、本月未超预算时才调用 LLM，否则空转
（提醒自动回退关键词规则，见 ``app/services/ai/status.py``）。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.news_item import NewsItem
from app.services.ai.context import load_portfolio_context
from app.services.ai.impact import NewsImpactService, impact_to_dict
from app.services.ai.llm_json import FunnelModel, resolve_funnel_model
from app.services.ai.screen import NewsScreenService
from app.services.ai.sectors import SectorInferenceService
from app.services.ai.status import FUNNEL_WORKER_NAME
from app.services.llm_cost import budget_status
from app.workers.base_worker import BaseWorker

# 超过这个时长的新闻只分析不提醒：首次启用时会补跑 24 小时内的存量新闻，避免一次性刷出旧提醒。
ALERT_MAX_NEWS_AGE = timedelta(hours=6)
SCREEN_BATCHES_PER_CYCLE = 3


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _news_payload(item: NewsItem, title_zh: str | None = None) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "title_zh": title_zh,
        "summary": item.summary,
        "source_name": item.source_name,
        "market": item.market,
    }


class AiFunnelWorker(BaseWorker):
    worker_name = FUNNEL_WORKER_NAME

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        alert_service: Any | None = None,
        model_resolver: Callable[[Session], FunnelModel | None] = resolve_funnel_model,
        clock: Callable[[], datetime] = _utc_now,
        max_attempts: int | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory)
        self._alert_service = alert_service
        self._model_resolver = model_resolver
        self._clock = clock
        self._max_attempts = max_attempts

    def get_interval(self) -> float:
        return get_settings().ai_funnel_interval_seconds

    def _alerts(self) -> Any:
        if self._alert_service is None:
            from app.services.alert_service import get_alert_service

            self._alert_service = get_alert_service()
        return self._alert_service

    def do_cycle(self) -> int:
        settings = get_settings()
        if not settings.ai_funnel_enabled:
            return 0
        max_attempts = self._max_attempts or settings.ai_max_attempts
        now = self._clock()
        with self.session_factory() as session:
            model = self._model_resolver(session)
            if model is None or budget_status(session, now).over_budget:
                return 0

            SectorInferenceService(session, model.provider).infer_missing(limit=1)
            session.commit()
            context = load_portfolio_context(session)

            screen_service = NewsScreenService(
                session,
                model.provider,
                model_name=model.model_name,
                batch_size=settings.ai_screen_batch_size,
                lookback_hours=settings.ai_screen_lookback_hours,
                max_attempts=max_attempts,
                clock=self._clock,
            )
            processed = 0
            fallback_ids: list[int] = []
            for _ in range(SCREEN_BATCHES_PER_CYCLE):
                outcome = screen_service.screen_once(context)
                session.commit()
                processed += outcome.screened
                fallback_ids.extend(outcome.exhausted)
                if outcome.screened + outcome.failed < settings.ai_screen_batch_size:
                    break

            impact_service = NewsImpactService(
                session,
                model.provider,
                model_name=model.model_name,
                daily_limit=settings.ai_impact_daily_limit,
                min_importance=settings.ai_impact_min_importance,
                max_attempts=max_attempts,
                body_max_chars=settings.ai_body_max_chars,
                correction_examples=settings.ai_correction_examples,
                clock=self._clock,
            )
            outcomes = impact_service.analyze_pending(context, limit=settings.ai_impact_per_cycle)
            session.commit()

            alert_calls: list[dict[str, Any]] = []
            for outcome in outcomes:
                if not self._is_fresh(outcome.news, now):
                    continue
                if outcome.ok:
                    processed += 1
                    alert_calls.append(
                        {
                            "news": _news_payload(outcome.news, outcome.screen.title_zh if outcome.screen else None),
                            "overseas": bool(outcome.screen and outcome.screen.overseas),
                            "major": bool(outcome.analysis.major),
                            "view": outcome.analysis.view,
                            "impacts": [impact_to_dict(impact) for impact in outcome.impacts],
                        }
                    )
                elif outcome.exhausted:
                    fallback_ids.append(outcome.news.id)
            fallback_items = [
                _news_payload(item)
                for item in session.scalars(select(NewsItem).where(NewsItem.id.in_(fallback_ids)))
                if self._is_fresh(item, now)
            ] if fallback_ids else []

        alerts = self._alerts()
        for call in alert_calls:
            alerts.on_news_impacts(
                call["news"], overseas=call["overseas"], major=call["major"], view=call["view"], impacts=call["impacts"]
            )
        if fallback_items:
            alerts.on_news_keyword_fallback(fallback_items)
        return processed

    @staticmethod
    def _is_fresh(item: NewsItem, now: datetime) -> bool:
        moment = _as_utc(item.published_at or item.fetched_at)
        return moment is None or now - moment <= ALERT_MAX_NEWS_AGE
