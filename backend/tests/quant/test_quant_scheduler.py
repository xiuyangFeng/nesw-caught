"""Phase C：每日盘后 quant 调度器。

契约（设计稿 §3.2 B5、计划 §C）：
- 交易日 + 到达 run_at 时刻 + 当日尚未跑过 scheduled run → 触发；
- 增量回填只覆盖行情库已存在的标的（有上限，防东财限流）；
- run_daily_task = 增量回填 + 跑流水线（trigger=scheduled）+ 发布事件；
- 手动触发端点 POST /api/quant/scheduler/run 直接执行一次当日任务。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.db.market_session import MarketSessionLocal
from app.db.session import SessionLocal
from app.models.market_data import DailyBar, FundFlowDaily, TradeCalendar
from app.models.quant import RecommendationItem, RecommendationRun
from app.services.quant.scheduler import QuantScheduler

SYMBOL = "000001.SZ"
OTHER = "600519.SH"


def _cleanup() -> None:
    with MarketSessionLocal() as market_session:
        market_session.query(FundFlowDaily).delete()
        market_session.query(DailyBar).delete()
        market_session.query(TradeCalendar).delete()
        market_session.commit()
    with SessionLocal() as session:
        session.query(RecommendationItem).delete()
        session.query(RecommendationRun).delete()
        session.commit()


def _fixed_now(dt: datetime) -> callable:
    return lambda: dt


def _seed_bars(symbol: str, *, last_date: date, days: int = 5, amount: float = 2e8) -> None:
    with MarketSessionLocal() as market_session:
        for i in range(days):
            trade_date = last_date - timedelta(days=days - 1 - i)
            market_session.add(
                DailyBar(
                    symbol=symbol,
                    trade_date=trade_date,
                    open=10,
                    high=10,
                    low=10,
                    close=10,
                    volume=1000,
                    amount=amount,
                )
            )
        market_session.commit()


def _seed_flow(symbol: str, *, last_date: date) -> None:
    with MarketSessionLocal() as market_session:
        market_session.add(FundFlowDaily(symbol=symbol, trade_date=last_date, main_net_inflow=8e7))
        market_session.commit()


def test_is_trading_day_uses_calendar_with_weekday_fallback() -> None:
    _cleanup()
    wednesday = date(2026, 8, 19)  # 星期三
    saturday = date(2026, 8, 22)   # 星期六
    with MarketSessionLocal() as market_session:
        # 日历覆盖周六为交易日（节假日调休场景）
        market_session.add(TradeCalendar(trade_date=saturday, is_open=1))
        market_session.commit()

    scheduler = QuantScheduler(session_factory=SessionLocal)
    # 有日历记录 → 用记录
    assert scheduler.is_trading_day(saturday) is True
    # 无记录 → 工作日 True / 周末 False
    assert scheduler.is_trading_day(wednesday) is True
    assert scheduler.is_trading_day(date(2026, 8, 23)) is False  # 星期日


def test_should_run_requires_trading_day_time_and_not_yet_run() -> None:
    _cleanup()
    run_at = "16:30"
    weekday_after = datetime(2026, 8, 19, 17, 0, tzinfo=UTC)   # 周三 17:00
    weekday_before = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)  # 周三 10:00
    weekend = datetime(2026, 8, 22, 17, 0, tzinfo=UTC)          # 周六 17:00

    scheduler = QuantScheduler(session_factory=SessionLocal, run_at=run_at, now_fn=_fixed_now(weekday_after))
    assert scheduler.should_run() is True

    scheduler_before = QuantScheduler(session_factory=SessionLocal, run_at=run_at, now_fn=_fixed_now(weekday_before))
    assert scheduler_before.should_run() is False

    scheduler_weekend = QuantScheduler(session_factory=SessionLocal, run_at=run_at, now_fn=_fixed_now(weekend))
    assert scheduler_weekend.should_run() is False

    # 当日已跑过 scheduled → 不再触发
    with SessionLocal() as session:
        session.add(
            RecommendationRun(
                run_date=weekday_after.date(),
                source_cutoff=weekday_after,
                trigger="scheduled",
                status="ok",
                scenario="real",
                dataset_version="t",
                factor_version="t",
                rule_version="t",
                code_commit="t",
                config_snapshot="{}",
                result_hash="h",
                started_at=weekday_after,
                finished_at=weekday_after,
            )
        )
        session.commit()
    assert scheduler.should_run() is False


def test_incremental_backfill_only_covers_existing_symbols() -> None:
    _cleanup()
    yesterday = date.today() - timedelta(days=1)
    _seed_bars(SYMBOL, last_date=yesterday)
    _seed_bars(OTHER, last_date=yesterday)

    fetched_symbols: list[str] = []

    def fake_bars(symbol, *, start, end, client=None):
        fetched_symbols.append(symbol)
        return [
            DailyBar(
                symbol=symbol,
                trade_date=date.today(),
                open=11,
                high=11,
                low=11,
                close=11,
                volume=1000,
                amount=2e8,
            )
        ]

    scheduler = QuantScheduler(
        session_factory=SessionLocal,
        fetch_bars=fake_bars,
        fetch_flow=lambda symbol, *, client=None: [],
        sleep_seconds=0,
        backfill_limit=10,
    )
    result = scheduler.incremental_backfill()
    assert set(fetched_symbols) == {SYMBOL, OTHER}
    assert result["bars"] == 2
    with MarketSessionLocal() as market_session:
        assert market_session.scalar(
            market_session.query(DailyBar)
            .filter_by(symbol=SYMBOL, trade_date=date.today())
            .exists()
            .select()
        ) is True


def test_run_daily_task_backfills_and_creates_scheduled_run() -> None:
    _cleanup()
    today = date.today()
    _seed_bars(SYMBOL, last_date=today - timedelta(days=1), days=130)
    _seed_flow(SYMBOL, last_date=today)

    def fake_bars(symbol, *, start, end, client=None):
        return [
            DailyBar(
                symbol=symbol,
                trade_date=today,
                open=10,
                high=10,
                low=10,
                close=10,
                volume=1000,
                amount=2e8,
            )
        ]

    scheduler = QuantScheduler(
        session_factory=SessionLocal,
        now_fn=_fixed_now(datetime(2026, 8, 19, 17, 0, tzinfo=UTC)),
        fetch_bars=fake_bars,
        fetch_flow=lambda symbol, *, client=None: [FundFlowDaily(symbol=symbol, trade_date=today, main_net_inflow=8e7)],
        sleep_seconds=0,
        backfill_limit=10,
    )
    result = scheduler.run_daily_task()
    assert result["run_id"] is not None
    with SessionLocal() as session:
        latest = session.query(RecommendationRun).order_by(RecommendationRun.id.desc()).first()
        assert latest is not None
        assert latest.trigger == "scheduled"
        assert latest.status == "ok"
    # 事件已发布（HybridEventBus 进程内广播不抛错即可）
    assert "backfill" in result
