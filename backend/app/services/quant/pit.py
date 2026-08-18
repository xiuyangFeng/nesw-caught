"""point-in-time 可见性：只有 available_at <= signal_cutoff 的记录能生成当时信号。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.services.quant.contracts import FinancialFact


def is_available(available_at: datetime, signal_cutoff: datetime) -> bool:
    return available_at <= signal_cutoff


def select_fact_for_signal(
    facts: Sequence[FinancialFact],
    *,
    symbol: str,
    metric_key: str,
    signal_cutoff: datetime,
) -> FinancialFact | None:
    visible = [
        fact
        for fact in facts
        if fact.symbol == symbol
        and fact.metric_key == metric_key
        and is_available(fact.available_at, signal_cutoff)
    ]
    if not visible:
        return None
    return max(visible, key=lambda fact: (fact.revision_no, fact.available_at))


def select_fact_for_display(
    facts: Sequence[FinancialFact],
    *,
    symbol: str,
    metric_key: str,
) -> FinancialFact | None:
    matching = [fact for fact in facts if fact.symbol == symbol and fact.metric_key == metric_key]
    if not matching:
        return None
    return max(matching, key=lambda fact: (fact.revision_no, fact.available_at))
