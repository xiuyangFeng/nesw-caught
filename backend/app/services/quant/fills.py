"""T 日收盘后信号最早 T+1 开盘成交；涨停开盘或停牌不成交。"""

from __future__ import annotations

from datetime import date

from app.services.quant.contracts import Bar, Board, FillDecision
from app.services.quant.trading_rules import is_limit_up_open, t_plus_n


def simulate_signal_fill(
    *,
    signal_date: date,
    next_open_bar: Bar | None,
    prev_close: float,
    board: Board,
    halted: bool,
) -> FillDecision:
    del signal_date
    if t_plus_n(board) < 1:
        return FillDecision(filled=False, fill_price=None, reason="unsupported_t_plus")
    if halted:
        return FillDecision(filled=False, fill_price=None, reason="halted")
    if next_open_bar is None:
        return FillDecision(filled=False, fill_price=None, reason="no_next_bar")
    if is_limit_up_open(next_open_bar.open, prev_close, board, next_open_bar.trade_date):
        locked = (
            next_open_bar.high == next_open_bar.low == next_open_bar.open
            or next_open_bar.volume == 0
        )
        if locked:
            return FillDecision(filled=False, fill_price=None, reason="limit_up_unfilled")
    return FillDecision(filled=True, fill_price=next_open_bar.open, reason="filled_t1_open")
