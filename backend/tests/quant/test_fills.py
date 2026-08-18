"""板块涨跌停、停牌与 T+1：信号日收盘后最早下一可交易日开盘成交。"""

from datetime import date

from app.services.quant.contracts import Bar, Board
from app.services.quant.fills import simulate_signal_fill
from app.services.quant.trading_rules import price_limit_pct, t_plus_n


def test_price_limits_differ_by_board() -> None:
    as_of = date(2026, 7, 6)
    assert price_limit_pct(Board.MAIN, as_of) == 0.10
    assert price_limit_pct(Board.CHINEXT, as_of) == 0.20
    assert price_limit_pct(Board.STAR, as_of) == 0.20
    assert price_limit_pct(Board.BSE, as_of) == 0.30
    assert t_plus_n(Board.MAIN, as_of) == 1


def test_t1_open_fills_at_next_session_open() -> None:
    nxt = Bar(
        symbol="600519.SH",
        trade_date=date(2026, 4, 14),
        open=1700.0,
        high=1710.0,
        low=1690.0,
        close=1705.0,
        volume=1_000_000,
        amount=1.7e9,
    )
    decision = simulate_signal_fill(
        signal_date=date(2026, 4, 13),
        next_open_bar=nxt,
        prev_close=1680.0,
        board=Board.MAIN,
        halted=False,
    )
    assert decision.filled is True
    assert decision.fill_price == 1700.0
    assert decision.reason == "filled_t1_open"


def test_limit_up_open_does_not_fill() -> None:
    prev_close = 10.0
    limit_open = 11.0  # 主板 10%
    nxt = Bar(
        symbol="600000.SH",
        trade_date=date(2026, 4, 14),
        open=limit_open,
        high=limit_open,
        low=limit_open,
        close=limit_open,
        volume=0,
        amount=0,
    )
    decision = simulate_signal_fill(
        signal_date=date(2026, 4, 13),
        next_open_bar=nxt,
        prev_close=prev_close,
        board=Board.MAIN,
        halted=False,
    )
    assert decision.filled is False
    assert decision.fill_price is None
    assert decision.reason == "limit_up_unfilled"


def test_chinext_20pct_limit_up_is_not_main_board_10pct() -> None:
    prev_close = 10.0
    nxt = Bar(
        symbol="300750.SZ",
        trade_date=date(2026, 4, 14),
        open=11.0,
        high=11.5,
        low=10.8,
        close=11.2,
        volume=2_000_000,
        amount=2.2e8,
    )
    decision = simulate_signal_fill(
        signal_date=date(2026, 4, 13),
        next_open_bar=nxt,
        prev_close=prev_close,
        board=Board.CHINEXT,
        halted=False,
    )
    assert decision.filled is True
    assert decision.fill_price == 11.0


def test_halted_name_does_not_fill() -> None:
    nxt = Bar(
        symbol="000001.SZ",
        trade_date=date(2026, 4, 14),
        open=10.0,
        high=10.0,
        low=10.0,
        close=10.0,
        volume=0,
        amount=0,
    )
    decision = simulate_signal_fill(
        signal_date=date(2026, 4, 13),
        next_open_bar=nxt,
        prev_close=10.0,
        board=Board.MAIN,
        halted=True,
    )
    assert decision.filled is False
    assert decision.reason == "halted"
