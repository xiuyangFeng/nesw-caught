"""模拟盘撮合：复用 fills.py，确认后才成交。"""

from __future__ import annotations

from app.services.quant.contracts import Bar, Board
from app.services.quant.fills import simulate_signal_fill


def place_order(
    *,
    confirmed: bool,
    signal_date,
    next_open_bar: Bar | None,
    prev_close: float,
    board: Board,
    halted: bool,
) -> dict:
    if not confirmed:
        return {"status": "pending_confirm", "filled": False, "reason": "needs_user_confirm"}
    fill = simulate_signal_fill(
        signal_date=signal_date,
        next_open_bar=next_open_bar,
        prev_close=prev_close,
        board=board,
        halted=halted,
    )
    if not fill.filled:
        return {"status": "rejected", "filled": False, "reason": fill.reason}
    return {"status": "filled", "filled": True, "price": fill.fill_price, "reason": fill.reason}
