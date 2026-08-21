"""每日盘后量化调度：交易日到达设定时刻后增量回填当日行情并跑真实选票流水线。

设计稿 §3.2 B5：
- 交易日（trade_calendar 判定，缺省按工作日）且本地时间 >= run_at、当日尚未跑过
  scheduled run → 触发；
- 增量回填只覆盖行情库已存在的标的（有上限，防东财限流），断点由
  upsert 的幂等语义兜住；
- run_daily_task = 增量回填 + 流水线（trigger=scheduled）+ 发布事件；
- 手动触发端点复用同一 run_daily_task，保证两条路径行为一致。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.market_session import MarketSessionLocal
from app.models.market_data import DailyBar, TradeCalendar
from app.models.quant import RecommendationRun
from app.services.event_bus import get_event_bus
from app.services.quant.market_data.backfill import (
    upsert_daily_bars,
    upsert_financial_facts,
    upsert_fund_flow,
)
from app.services.quant.market_data.eastmoney_fund_flow import fetch_fund_flow
from app.services.quant.market_data.eastmoney_history import fetch_daily_bars
from app.services.quant_desk_service import QuantDeskService

logger = logging.getLogger("app.services.quant.scheduler")


class QuantScheduler:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        logger: logging.Logger | None = None,
        run_at: str = "16:30",
        backfill_limit: int = 50,
        sleep_seconds: float = 0.4,
        now_fn: Callable[[], datetime] | None = None,
        fetch_bars: Callable = fetch_daily_bars,
        fetch_flow: Callable = fetch_fund_flow,
        include_financials: bool = False,
        fetch_financials: Callable | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.logger = logger or logging.getLogger(__name__)
        self.run_at = run_at
        self.backfill_limit = backfill_limit
        self.sleep_seconds = sleep_seconds
        self.now_fn = now_fn or (lambda: datetime.now())
        self.fetch_bars = fetch_bars
        self.fetch_flow = fetch_flow
        self.include_financials = include_financials
        if include_financials:
            from app.services.quant.market_data.eastmoney_financials import (
                fetch_financials as _real,
            )

            self.fetch_financials = fetch_financials or _real

    def now(self) -> datetime:
        return self.now_fn()

    def is_trading_day(self, day: date) -> bool:
        with MarketSessionLocal() as market_session:
            row = market_session.get(TradeCalendar, day)
        if row is not None:
            return bool(row.is_open)
        # 日历未覆盖时按工作日兜底；周末视作休市。
        return day.weekday() < 5

    def last_scheduled_run_date(self) -> date | None:
        with self.session_factory() as session:
            row = session.scalar(
                select(RecommendationRun)
                .where(RecommendationRun.trigger == "scheduled")
                .order_by(RecommendationRun.id.desc())
                .limit(1)
            )
            return row.run_date if row is not None else None

    def should_run(self) -> bool:
        now = self.now()
        if not self.is_trading_day(now.date()):
            return False
        if now.strftime("%H:%M") < self.run_at:
            return False
        if self.last_scheduled_run_date() == now.date():
            return False
        return True

    def incremental_backfill(self) -> dict:
        """只补行情库已有标的：按「最新 bar 日期最旧优先」取前 limit 个，抓取其后到今日的日线与资金流。"""
        with MarketSessionLocal() as market_session:
            rows = market_session.execute(
                select(DailyBar.symbol, func.max(DailyBar.trade_date))
                .group_by(DailyBar.symbol)
                .order_by(func.max(DailyBar.trade_date).asc())
                .limit(self.backfill_limit)
            ).all()
        today = self.now().date()
        bars = 0
        flows = 0
        financials = 0
        failures = 0
        for symbol, latest_date in rows:
            if latest_date >= today:
                continue
            start = latest_date + timedelta(days=1)
            try:
                new_bars = self.fetch_bars(symbol, start=start, end=today)
                with MarketSessionLocal() as market_session:
                    bars += upsert_daily_bars(market_session, new_bars)
                    market_session.commit()
            except Exception as exc:  # noqa: BLE001 - 单标的失败不阻断整批
                self.logger.warning("quant incremental backfill bars failed for %s: %s", symbol, exc)
                failures += 1
            try:
                new_flows = self.fetch_flow(symbol)
                with MarketSessionLocal() as market_session:
                    flows += upsert_fund_flow(market_session, new_flows)
                    market_session.commit()
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("quant incremental backfill flow failed for %s: %s", symbol, exc)
                failures += 1
            if self.include_financials:
                try:
                    new_facts = self.fetch_financials(symbol)
                    with MarketSessionLocal() as market_session:
                        financials += upsert_financial_facts(market_session, new_facts)
                        market_session.commit()
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning("quant incremental backfill financials failed for %s: %s", symbol, exc)
                    failures += 1
            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)
        return {"bars": bars, "fund_flow": flows, "financial_facts": financials, "failures": failures, "symbols": len(rows)}

    def run_daily_task(self) -> dict:
        backfill = self.incremental_backfill()
        run_id: int | None = None
        status = "unknown"
        with self.session_factory() as session:
            view = QuantDeskService().run(session, scenario="real", trigger="scheduled")
            session.commit()
            if view.run is not None:
                run_id = view.run.id
                status = view.run.status
        try:
            get_event_bus().publish(
                "quant.pipeline_scheduled",
                {"run_id": run_id, "status": status, "backfill": backfill},
            )
        except Exception as exc:  # noqa: BLE001 - 事件层不可用不阻断任务本身
            self.logger.warning("quant scheduler event publish failed: %s", exc)
        return {"run_id": run_id, "status": status, "backfill": backfill}
