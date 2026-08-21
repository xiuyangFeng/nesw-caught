"""三 sleeve 规则因子。LLM 不得改分数。"""

from __future__ import annotations

from dataclasses import dataclass

FACTOR_REGISTRY = {
    "main_inflow_1d": {"sleeve": "trend_flow", "horizon": "5d"},
    "news_novelty": {"sleeve": "event_catalyst", "horizon": "5d"},
    "gap_unfilled": {"sleeve": "fundamental_revalue", "horizon": "60d"},
    "net_profit_yoy": {"sleeve": "fundamental_revalue", "horizon": "60d"},
    "revenue_yoy": {"sleeve": "fundamental_revalue", "horizon": "60d"},
    "roe": {"sleeve": "fundamental_revalue", "horizon": "60d"},
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


def score_fundamental(
    *,
    net_profit_yoy: float | None,
    revenue_yoy: float | None,
    roe: float | None,
    covered: bool,
) -> SleeveScore:
    """基本面重估打分（Phase D 实装）。

    覆盖不足时维持显式 gap 不编造；有数据时按净利同比/营收同比/ROE 加权给分。
    治理约定：fundamental sleeve 暂不晋级 qualified（阈值治理后续再做），
    只产 WATCH/候选，reason_code 区分过线观察与未过线。
    """
    if not covered:
        return SleeveScore(
            sleeve="fundamental_revalue",
            score=0.0,
            breakdown={"financial_coverage": 0.0},
            qualify=False,
            reason_code="fundamental_gap_no_financials",
        )

    def _cap01(value: float | None, ceiling: float) -> float:
        if value is None:
            return 0.0
        return max(-1.0, min(1.0, value / ceiling))

    profit_score = _cap01(net_profit_yoy, 0.5)  # 净利同比 ±50% 封顶
    revenue_score = _cap01(revenue_yoy, 0.5)
    roe_score = 0.0 if roe is None else max(0.0, min(1.0, roe / 20.0))  # ROE 20% 满分
    score = 0.4 * profit_score + 0.3 * revenue_score + 0.3 * roe_score
    breakdown: dict[str, float] = {
        "financial_coverage": 1.0,
        "net_profit_yoy": net_profit_yoy or 0.0,
        "revenue_yoy": revenue_yoy or 0.0,
        "roe": roe or 0.0,
    }
    watch = score >= 0.25
    return SleeveScore(
        sleeve="fundamental_revalue",
        score=round(score, 6),
        breakdown=breakdown,
        qualify=False,  # 治理约定：基本面 sleeve 暂不晋级
        reason_code="fundamental_watch_above_threshold" if watch else "fundamental_below_threshold",
    )
