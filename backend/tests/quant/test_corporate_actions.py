"""除权：只用当时已知的公司行动构造 total-return，禁止用最终后复权回算。"""

from datetime import UTC, date, datetime

from app.services.quant.contracts import Bar, CorporateAction
from app.services.quant.corporate_actions import period_total_return


def _bar(trade_date: date, close: float) -> Bar:
    return Bar(
        symbol="600519.SH",
        trade_date=trade_date,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1_000,
        amount=close * 1_000,
    )


def test_known_bonus_issue_keeps_total_return_flat() -> None:
    bars = [_bar(date(2026, 5, 8), 20.0), _bar(date(2026, 6, 2), 10.0)]
    action = CorporateAction(
        symbol="600519.SH",
        action_type="stock_dividend",
        ex_date=date(2026, 6, 2),
        available_at=datetime(2026, 5, 20, 8, 0, tzinfo=UTC),
        share_ratio=1.0,
    )
    cutoff = datetime(2026, 5, 21, 7, 30, tzinfo=UTC)

    tr = period_total_return(
        bars, [action], start=date(2026, 5, 8), end=date(2026, 6, 2), signal_cutoff=cutoff
    )
    assert abs(tr) < 1e-9


def test_unknown_at_cutoff_bonus_issue_is_not_applied() -> None:
    bars = [_bar(date(2026, 5, 8), 20.0), _bar(date(2026, 6, 2), 10.0)]
    action = CorporateAction(
        symbol="600519.SH",
        action_type="stock_dividend",
        ex_date=date(2026, 6, 2),
        available_at=datetime(2026, 5, 20, 8, 0, tzinfo=UTC),
        share_ratio=1.0,
    )
    cutoff_before_announce = datetime(2026, 5, 10, 7, 30, tzinfo=UTC)

    tr = period_total_return(
        bars,
        [action],
        start=date(2026, 5, 8),
        end=date(2026, 6, 2),
        signal_cutoff=cutoff_before_announce,
    )
    assert tr == -0.5
