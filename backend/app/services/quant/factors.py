"""三 sleeve 规则因子。LLM 不得改分数。"""

from __future__ import annotations

from dataclasses import dataclass

FACTOR_REGISTRY = {
    "main_inflow_1d": {"sleeve": "trend_flow", "horizon": "5d"},
    "news_novelty": {"sleeve": "event_catalyst", "horizon": "5d"},
    "gap_unfilled": {"sleeve": "fundamental_revalue", "horizon": "60d"},
}


@dataclass(frozen=True)
class SleeveScore:
    sleeve: str
    score: float
    breakdown: dict[str, float]
    qualify: bool
    reason_code: str


def score_event(*, novelty: float, materiality: float, grade: str) -> SleeveScore:
    quality = {"A": 1.0, "B": 0.8, "C": 0.5, "D": 0.15}[grade]
    value = novelty * materiality * quality
    qualify = value >= 0.4 and grade in {"A", "B"}
    return SleeveScore(
        sleeve="event_catalyst",
        score=value,
        breakdown={"news_novelty": novelty, "materiality": materiality, "grade": quality},
        qualify=qualify,
        reason_code="event_qualified" if qualify else "event_below_threshold_or_weak_evidence",
    )


def score_trend(*, inflow: float | None, adv: float | None) -> SleeveScore:
    inflow_z = 0.0 if inflow is None else max(-1.0, min(1.0, inflow / 50_000_000))
    liq = 0.0 if adv is None else max(0.0, min(1.0, adv / 100_000_000))
    value = 0.6 * abs(inflow_z) + 0.4 * liq
    qualify = inflow is not None and inflow > 50_000_000 and liq >= 0.3
    return SleeveScore(
        sleeve="trend_flow",
        score=value,
        breakdown={"main_inflow_1d": inflow or 0.0, "adv": adv or 0.0},
        qualify=qualify,
        reason_code="trend_qualified" if qualify else "trend_liquidity_or_flow_short",
    )


def score_fundamental(*, gap: str | None) -> SleeveScore:
    qualify = False
    return SleeveScore(
        sleeve="fundamental_revalue",
        score=0.0,
        breakdown={"financial_coverage": 0.0},
        qualify=qualify,
        reason_code="fundamental_gap_no_financials" if gap else "fundamental_below_threshold",
    )
