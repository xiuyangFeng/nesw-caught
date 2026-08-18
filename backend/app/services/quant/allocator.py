"""组合风险预算。排名不等于仓位。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProposedPosition:
    symbol: str
    sleeve: str
    weight: float
    reject_reason: str | None = None


def allocate(
    items: list[tuple[str, str, float]],
    *,
    max_symbol_weight: float = 0.08,
    max_sleeve_weight: float = 0.5,
    min_cash: float = 0.1,
    max_positions: int = 12,
) -> tuple[list[ProposedPosition], float]:
    """items: symbol, sleeve, dummy_vol (higher vol -> lower weight)."""
    ranked = sorted(items, key=lambda row: row[2])[:max_positions]
    if not ranked:
        return [], 1.0
    raw = [(symbol, sleeve, 1.0 / max(vol, 1e-6)) for symbol, sleeve, vol in ranked]
    total = sum(item[2] for item in raw) or 1.0
    positions: list[ProposedPosition] = []
    sleeve_used: dict[str, float] = {}
    invested = 0.0
    for symbol, sleeve, score in raw:
        remaining_cash_cap = 1.0 - min_cash - invested
        if remaining_cash_cap <= 0:
            positions.append(ProposedPosition(symbol, sleeve, 0, "cash_floor"))
            continue
        sleeve_cap = max_sleeve_weight - sleeve_used.get(sleeve, 0.0)
        weight = min(max_symbol_weight, remaining_cash_cap, sleeve_cap, score / total)
        if weight <= 0:
            positions.append(ProposedPosition(symbol, sleeve, 0, "sleeve_or_cash_cap"))
            continue
        sleeve_used[sleeve] = sleeve_used.get(sleeve, 0.0) + weight
        invested += weight
        positions.append(ProposedPosition(symbol, sleeve, round(weight, 6)))
    return positions, round(max(min_cash, 1.0 - invested), 6)
