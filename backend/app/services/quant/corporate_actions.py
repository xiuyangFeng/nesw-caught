"""用不复权价格 + 当时已知公司行动构造区间 total-return。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from app.services.quant.contracts import Bar, CorporateAction
from app.services.quant.pit import is_available


def pit_known_actions(
    actions: Sequence[CorporateAction], signal_cutoff: datetime
) -> list[CorporateAction]:
    return [action for action in actions if is_available(action.available_at, signal_cutoff)]


def period_total_return(
    bars: Sequence[Bar],
    actions: Sequence[CorporateAction],
    *,
    start: date,
    end: date,
    signal_cutoff: datetime,
) -> float:
    by_date = {bar.trade_date: bar.close for bar in bars}
    start_close = by_date[start]
    end_close = by_date[end]
    if start_close == 0:
        raise ValueError("start close is zero")

    share_multiplier = 1.0
    cash_received = 0.0
    for action in pit_known_actions(actions, signal_cutoff):
        if action.ex_date <= start or action.ex_date > end:
            continue
        share_multiplier *= 1.0 + action.share_ratio
        cash_received += action.cash_ratio * share_multiplier
    return (end_close * share_multiplier + cash_received) / start_close - 1.0
