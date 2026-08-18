"""当时有效的交易规则。首版覆盖 2026-07-06 起沪深北涨跌幅与 T+1。"""

from __future__ import annotations

from datetime import date

from app.services.quant.contracts import Board

_PRICE_LIMIT_PCT: dict[Board, float] = {
    Board.MAIN: 0.10,
    Board.CHINEXT: 0.20,
    Board.STAR: 0.20,
    Board.BSE: 0.30,
}

RULE_VERSION = "cn-exchanges-2026-07-06"


def price_limit_pct(board: Board, as_of: date | None = None) -> float:
    del as_of  # 首版仅一套 2026-07-06 规则；后续按 trading_rule_version 查区间。
    return _PRICE_LIMIT_PCT[board]


def t_plus_n(board: Board, as_of: date | None = None) -> int:
    del board, as_of
    return 1


def is_limit_up_open(open_px: float, prev_close: float, board: Board, as_of: date | None = None) -> bool:
    if prev_close <= 0:
        return False
    limit_px = round(prev_close * (1 + price_limit_pct(board, as_of)), 2)
    return round(open_px, 2) >= limit_px
