"""日线/资金流回填：分批、断点续传、不写主库。"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.market_session import MarketSessionLocal
from app.models.market_data import DailyBar, FundFlowDaily, TradeCalendar
from app.services.quant.market_data.eastmoney_fund_flow import fetch_fund_flow
from app.services.quant.market_data.eastmoney_history import fetch_daily_bars

logger = logging.getLogger(__name__)


def upsert_daily_bars(session, bars) -> int:
    count = 0
    for bar in bars:
        stmt = (
            sqlite_insert(DailyBar)
            .values(
                symbol=bar.symbol,
                trade_date=bar.trade_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                amount=bar.amount,
                turnover_rate=bar.turnover_rate,
            )
            .on_conflict_do_update(
                index_elements=["symbol", "trade_date"],
                set_={
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "amount": bar.amount,
                    "turnover_rate": bar.turnover_rate,
                },
            )
        )
        session.execute(stmt)
        count += 1
    _refresh_calendar(session, [bar.trade_date for bar in bars])
    return count


def upsert_fund_flow(session, rows) -> int:
    count = 0
    for row in rows:
        stmt = (
            sqlite_insert(FundFlowDaily)
            .values(
                symbol=row.symbol,
                trade_date=row.trade_date,
                main_net_inflow=row.main_net_inflow,
                super_large_net=row.super_large_net,
                large_net=row.large_net,
                medium_net=row.medium_net,
                small_net=row.small_net,
                main_net_pct=row.main_net_pct,
            )
            .on_conflict_do_update(
                index_elements=["symbol", "trade_date"],
                set_={
                    "main_net_inflow": row.main_net_inflow,
                    "super_large_net": row.super_large_net,
                    "large_net": row.large_net,
                    "medium_net": row.medium_net,
                    "small_net": row.small_net,
                    "main_net_pct": row.main_net_pct,
                },
            )
        )
        session.execute(stmt)
        count += 1
    return count


def _refresh_calendar(session, dates: Sequence[date]) -> None:
    for trade_date in set(dates):
        stmt = (
            sqlite_insert(TradeCalendar)
            .values(trade_date=trade_date, is_open=1)
            .on_conflict_do_nothing(index_elements=["trade_date"])
        )
        session.execute(stmt)


def _load_checkpoint(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return set(payload.get("done", []))


def _save_checkpoint(path: Path, done: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"done": sorted(done)}, ensure_ascii=False), encoding="utf-8")


def backfill_symbols(
    symbols: Sequence[str],
    *,
    start: date,
    end: date,
    checkpoint_path: Path,
    sleep_seconds: float = 0.2,
    fetch_bars: Callable = fetch_daily_bars,
    fetch_flow: Callable = fetch_fund_flow,
) -> dict[str, int]:
    done = _load_checkpoint(checkpoint_path)
    bar_count = 0
    flow_count = 0
    failures = 0
    for symbol in symbols:
        if symbol in done:
            continue
        try:
            bars = fetch_bars(symbol, start=start, end=end)
            flows = fetch_flow(symbol)
            with MarketSessionLocal() as session:
                bar_count += upsert_daily_bars(session, bars)
                flow_count += upsert_fund_flow(session, flows)
                session.commit()
            done.add(symbol)
            _save_checkpoint(checkpoint_path, done)
        except Exception:
            logger.exception("backfill failed for %s", symbol)
            failures += 1
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return {"bars": bar_count, "fund_flow": flow_count, "failures": failures, "done": len(done)}
