from datetime import date
from pathlib import Path

from app.db.market_session import MarketSessionLocal
from app.models.market_data import DailyBar, FundFlowDaily
from app.services.quant.market_data.backfill import backfill_symbols
from app.services.quant.market_data.eastmoney_fund_flow import ParsedFundFlow
from app.services.quant.market_data.eastmoney_history import ParsedDailyBar


def test_backfill_is_resumable_and_writes_market_db(tmp_path: Path) -> None:
    bar = ParsedDailyBar(
        symbol="600519.SH",
        trade_date=date(2026, 4, 10),
        open=1,
        high=1,
        low=1,
        close=1,
        volume=1,
        amount=1,
        turnover_rate=None,
    )
    flow = ParsedFundFlow(
        symbol="600519.SH",
        trade_date=date(2026, 4, 10),
        main_net_inflow=10,
        super_large_net=1,
        large_net=2,
        medium_net=3,
        small_net=4,
        main_net_pct=0.1,
    )
    checkpoint = tmp_path / "ckpt.json"
    first = backfill_symbols(
        ["600519.SH"],
        start=date(2026, 1, 1),
        end=date(2026, 4, 10),
        checkpoint_path=checkpoint,
        sleep_seconds=0,
        fetch_bars=lambda symbol, start, end: [bar],
        fetch_flow=lambda symbol: [flow],
    )
    second = backfill_symbols(
        ["600519.SH"],
        start=date(2026, 1, 1),
        end=date(2026, 4, 10),
        checkpoint_path=checkpoint,
        sleep_seconds=0,
        fetch_bars=lambda symbol, start, end: (_ for _ in ()).throw(AssertionError("should skip")),
        fetch_flow=lambda symbol: [],
    )
    assert first["done"] == 1
    assert second["bars"] == 0
    with MarketSessionLocal() as session:
        stored = session.get(DailyBar, ("600519.SH", date(2026, 4, 10)))
        flow_row = session.get(FundFlowDaily, ("600519.SH", date(2026, 4, 10)))
    assert stored is not None
    assert stored.close == 1
    assert flow_row is not None
    assert flow_row.main_net_inflow == 10
