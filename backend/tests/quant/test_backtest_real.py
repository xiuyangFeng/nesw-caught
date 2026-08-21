"""回测真实化：真实行情库 bars/资金流驱动 walk-forward，输出净值曲线与交易明细。

契约（设计稿 §3.2 B1）：
- run_backtest 只吃 market_data.db 真实数据，不再喂合成 Bar；
- 报告含 equity_curve（首点 1.0）与逐笔 trades；
- bar 数不足时显式 coverage_error，不降级为合成数据；
- 治理不变：恒 exploratory、qualified=False。
"""

from __future__ import annotations

from datetime import date, timedelta

from app.db.market_session import MarketSessionLocal
from app.models.market_data import DailyBar, FundFlowDaily
from app.services.quant_desk_service import QuantDeskService

SYMBOL = "000001.SZ"
DSL = {
    "sleeve": "trend_flow",
    "horizon": "20d",
    "logic": "and",
    "conditions": [{"factor": "main_inflow_1d", "op": ">", "value": 1}],
}


def _cleanup() -> None:
    with MarketSessionLocal() as market_session:
        market_session.query(FundFlowDaily).delete()
        market_session.query(DailyBar).delete()
        market_session.commit()


def _seed_real_bars(*, days: int = 130, base_close: float = 10.0) -> None:
    """隔日收盘价交替 +1/-0.5 的确定性序列：信号翻转必然产生开平仓。"""
    start = date.today() - timedelta(days=days - 1)
    with MarketSessionLocal() as market_session:
        for i in range(days):
            trade_date = start + timedelta(days=i)
            close = base_close + (1.0 if i % 4 < 2 else 0.0)
            market_session.add(
                DailyBar(
                    symbol=SYMBOL,
                    trade_date=trade_date,
                    open=close,
                    high=close + 0.2,
                    low=close - 0.2,
                    close=close,
                    volume=1000,
                    amount=2e8,
                )
            )
        market_session.commit()


def _seed_fund_flow(*, days: int, inflow_days: int) -> None:
    """前 inflow_days 天主力净流入 8e7（信号真），之后 0（信号假触发平仓）。"""
    start = date.today() - timedelta(days=days - 1)
    with MarketSessionLocal() as market_session:
        for i in range(days):
            market_session.add(
                FundFlowDaily(
                    symbol=SYMBOL,
                    trade_date=start + timedelta(days=i),
                    main_net_inflow=8e7 if i < inflow_days else 0.0,
                )
            )
        market_session.commit()


def test_backtest_uses_real_bars_and_reports_curve_and_trades() -> None:
    _cleanup()
    _seed_real_bars(days=130)
    _seed_fund_flow(days=130, inflow_days=60)

    with MarketSessionLocal() as market_session:
        pass
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        view = QuantDeskService().run_backtest(session, None, DSL, symbol=SYMBOL)

    assert view.symbol == SYMBOL
    assert view.coverage_error is None
    assert view.bars_used == 130
    assert view.exploratory is True
    assert view.qualified is False
    # 净值曲线首点为 1.0，日期为 ISO 字符串
    assert view.equity_curve, "equity_curve 不能为空"
    assert view.equity_curve[0]["equity"] == 1.0
    # 前半段信号为真、后半段为假：至少完成一次完整开平仓
    assert view.trades, "至少应有一笔完整交易"
    trade = view.trades[0]
    assert trade["signal_date"]
    assert trade["entry_date"]
    assert trade["entry_price"] > 0
    assert trade["exit_date"]
    assert trade["exit_price"] > 0
    assert trade["pnl"] is not None
    # 真实数据驱动：入场价来自真实 bar 开盘价（10 或 11 附近），绝不是合成 10.0/9.5
    assert trade["entry_price"] in (10.0, 11.0)
    # metrics 保留核心指标
    assert "net_return" in view.metrics
    assert "max_drawdown" in view.metrics


def test_backtest_insufficient_bars_returns_coverage_error() -> None:
    _cleanup()
    _seed_real_bars(days=10)

    from app.db.session import SessionLocal

    with SessionLocal() as session:
        view = QuantDeskService().run_backtest(session, None, DSL, symbol=SYMBOL)

    assert view.coverage_error is not None
    assert "回填" in view.coverage_error
    assert view.trades == []
    assert view.equity_curve == []
    assert view.bars_used == 10


def test_backtest_no_bars_returns_coverage_error() -> None:
    _cleanup()

    from app.db.session import SessionLocal

    with SessionLocal() as session:
        view = QuantDeskService().run_backtest(session, None, DSL, symbol=SYMBOL)

    assert view.coverage_error is not None
    assert view.bars_used == 0


def test_backtest_date_range_filters_bars() -> None:
    _cleanup()
    _seed_real_bars(days=130)
    _seed_fund_flow(days=130, inflow_days=60)
    end = date.today() - timedelta(days=40)
    start = end - timedelta(days=69)

    from app.db.session import SessionLocal

    with SessionLocal() as session:
        view = QuantDeskService().run_backtest(session, None, DSL, symbol=SYMBOL, start_date=start, end_date=end)

    assert view.coverage_error is None
    assert view.bars_used == 70
