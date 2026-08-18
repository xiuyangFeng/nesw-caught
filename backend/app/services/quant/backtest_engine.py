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
            else:
                unfilled += 1
        elif position and not signal:
            pnl = (nxt.open / entry_price) - 1.0
            equity *= 1.0 + pnl
            position = 0.0
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
    return {
        "net_return": round(equity - 1.0, 6),
        "max_drawdown": round(max_dd, 6),
        "trades": trades,
        "unfilled": unfilled,
        "exploratory": True,
        "qualified": False,
    }
