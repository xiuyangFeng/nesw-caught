"""Phase D：基本面 sleeve 真实打分（financial_fact 驱动）与 PIT 约束。"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.db.market_session import MarketSessionLocal
from app.models.market_data import DailyBar, FinancialFact, FundFlowDaily
from app.services.quant.contracts import CandidateState, RunStatus, RunVersions, Sleeve
from app.services.quant.recommendation.market_pipeline import run_market_pipeline
from app.services.quant.trading_rules import RULE_VERSION

SYMBOL = "000001.SZ"


def _cleanup() -> None:
    with MarketSessionLocal() as market_session:
        market_session.query(FinancialFact).delete()
        market_session.query(FundFlowDaily).delete()
        market_session.query(DailyBar).delete()
        market_session.commit()


def _versions(source_cutoff: datetime | None = None) -> RunVersions:
    return RunVersions(
        dataset_version="test-eastmoney-daily",
        factor_version="rule-v1",
        rule_version=RULE_VERSION,
        code_commit="test",
        config_snapshot={},
        source_cutoff=source_cutoff or datetime.now(UTC),
    )


def _seed_bars(days: int = 130, amount: float = 2e8) -> None:
    today = date.today()
    with MarketSessionLocal() as market_session:
        for i in range(days):
            market_session.add(
                DailyBar(
                    symbol=SYMBOL,
                    trade_date=today - timedelta(days=days - 1 - i),
                    open=10,
                    high=10,
                    low=10,
                    close=10,
                    volume=1000,
                    amount=amount,
                )
            )
        market_session.commit()


def _seed_financial(
    *,
    period_end: date,
    available_at: date,
    net_profit_yoy: float | None = 0.2,
    revenue_yoy: float | None = 0.1,
    roe: float | None = 15.0,
) -> None:
    with MarketSessionLocal() as market_session:
        for key, value in (
            ("net_profit_yoy", net_profit_yoy),
            ("revenue_yoy", revenue_yoy),
            ("roe", roe),
        ):
            market_session.add(
                FinancialFact(
                    symbol=SYMBOL,
                    period_end=period_end,
                    metric_key=key,
                    value=value,
                    available_at=available_at,
                )
            )
        market_session.commit()


def test_fundamental_candidate_watch_from_financials() -> None:
    _cleanup()
    _seed_bars()
    today = date.today()
    _seed_financial(
        period_end=date(today.year, 3, 31),
        available_at=today - timedelta(days=10),
        net_profit_yoy=1.0,
        revenue_yoy=0.33,
        roe=15.0,
    )

    result = run_market_pipeline(versions=_versions())
    assert result.status is RunStatus.OK
    fundamental = [item for item in result.items if item.sleeve is Sleeve.FUNDAMENTAL_REVALUE]
    assert len(fundamental) == 1
    item = fundamental[0]
    assert item.state is CandidateState.WATCH
    assert item.reason_code == "fundamental_watch_above_threshold"
    assert item.factor_breakdown["net_profit_yoy"] == 1.0
    assert item.factor_breakdown["roe"] == 15.0
    # 治理约定：基本面 sleeve 不晋级 qualified
    assert item not in result.qualified


def test_fundamental_gap_when_no_financials() -> None:
    _cleanup()
    _seed_bars()
    result = run_market_pipeline(versions=_versions())
    fundamental = [item for item in result.items if item.sleeve is Sleeve.FUNDAMENTAL_REVALUE]
    assert fundamental == []
    stage = next(s for s in result.stages if s.stage == "sleeve_fundamental_revalue")
    assert stage.detail["scored"] == 0
    assert stage.detail["gap_symbols"] >= 1


def test_fundamental_respects_pit_available_at() -> None:
    _cleanup()
    _seed_bars()
    today = date.today()
    # 未来披露日的财报：截点前不可见，不得用于打分
    _seed_financial(
        period_end=today.replace(year=today.year - 1, month=12, day=31),
        available_at=today + timedelta(days=30),
        net_profit_yoy=1.0,
        roe=30.0,
    )
    result = run_market_pipeline(versions=_versions())
    fundamental = [item for item in result.items if item.sleeve is Sleeve.FUNDAMENTAL_REVALUE]
    assert fundamental == []
