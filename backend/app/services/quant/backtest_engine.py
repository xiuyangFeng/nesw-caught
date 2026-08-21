"""自研日线回测。探索性结果不得标 qualified。"""

from __future__ import annotations

from datetime import date

from app.services.quant.contracts import Bar, Board
from app.services.quant.dsl import evaluate_dsl
from app.services.quant.fills import simulate_signal_fill


def walk_forward(
    *,
    dsl: dict,
    bars: list[Bar],
    board: Board,
    features_by_date: dict[date, dict[str, float]],
) -> dict:
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    trades = 0
    unfilled = 0
    position = 0.0
    entry_price = 0.0
    equity_curve: list[dict] = []
    trade_rows: list[dict] = []
    open_trade: dict | None = None
    for index, bar in enumerate(bars[:-1]):
        features = features_by_date.get(bar.trade_date, {})
        signal = evaluate_dsl(dsl, features)
        nxt = bars[index + 1]
        if signal and position == 0:
            fill = simulate_signal_fill(
                signal_date=bar.trade_date,
                next_open_bar=nxt,
                prev_close=bar.close,
                board=board,
                halted=False,
            )
            if fill.filled and fill.fill_price:
                position = 1.0
                entry_price = fill.fill_price
                trades += 1
                open_trade = {
                    "signal_date": bar.trade_date.isoformat(),
                    "entry_date": nxt.trade_date.isoformat(),
                    "entry_price": fill.fill_price,
                }
            else:
                unfilled += 1
        elif position and not signal:
            pnl = (nxt.open / entry_price) - 1.0
            equity *= 1.0 + pnl
            position = 0.0
            if open_trade is not None:
                open_trade.update(
                    {
                        "exit_date": nxt.trade_date.isoformat(),
                        "exit_price": nxt.open,
                        "pnl": round(pnl, 6),
                    }
                )
                trade_rows.append(open_trade)
                open_trade = None
            equity_curve.append({"date": nxt.trade_date.isoformat(), "equity": round(equity, 6)})
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
    # 期末仍持仓：按最后一根 bar 收盘价估值平仓，保证净值曲线闭合、不隐藏浮盈亏。
    if position and bars:
        last = bars[-1]
        pnl = (last.close / entry_price) - 1.0
        equity *= 1.0 + pnl
        if open_trade is not None:
            open_trade.update(
                {
                    "exit_date": last.trade_date.isoformat(),
                    "exit_price": last.close,
                    "pnl": round(pnl, 6),
                }
            )
            trade_rows.append(open_trade)
        equity_curve.append({"date": last.trade_date.isoformat(), "equity": round(equity, 6)})
    if bars and not equity_curve:
        equity_curve.append({"date": bars[0].trade_date.isoformat(), "equity": 1.0})
    return {
        "net_return": round(equity - 1.0, 6),
        "max_drawdown": round(max_dd, 6),
        "trades": trades,
        "unfilled": unfilled,
        "exploratory": True,
        "qualified": False,
        "equity_curve": equity_curve,
        "trade_rows": trade_rows,
    }
