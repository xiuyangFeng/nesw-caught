"""U0 历史证券切片与当日可交易池 U2。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from app.services.quant.contracts import SecurityMasterRow

DEFAULT_MIN_LIST_DAYS = 120
DEFAULT_MIN_MEDIAN_AMOUNT_20D = 100_000_000.0
_EXCLUDED_STATUS = frozenset({"halted", "delisted"})


def _effective_on(row: SecurityMasterRow, as_of: date) -> bool:
    if row.effective_from > as_of:
        return False
    if row.effective_to is not None and row.effective_to < as_of:
        return False
    return True


def securities_as_of(master: Sequence[SecurityMasterRow], as_of: date) -> list[SecurityMasterRow]:
    return [row for row in master if _effective_on(row, as_of)]


def build_u2(
    master: Sequence[SecurityMasterRow],
    as_of: date,
    *,
    min_list_days: int = DEFAULT_MIN_LIST_DAYS,
    min_median_amount_20d: float = DEFAULT_MIN_MEDIAN_AMOUNT_20D,
) -> list[str]:
    symbols: list[str] = []
    for row in securities_as_of(master, as_of):
        if row.status in _EXCLUDED_STATUS:
            continue
        if row.delist_date is not None and row.delist_date <= as_of:
            continue
        listed_days = (as_of - row.list_date).days
        if listed_days < min_list_days:
            continue
        if row.median_amount_20d is None or row.median_amount_20d < min_median_amount_20d:
            continue
        symbols.append(row.symbol)
    return symbols
