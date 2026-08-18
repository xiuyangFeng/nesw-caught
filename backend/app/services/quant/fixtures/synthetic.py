"""合成夹具：一个事件、一个趋势、一个基本面案例。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.services.quant.contracts import (
    Board,
    Candidate,
    CandidateState,
    Horizon,
    SecurityMasterRow,
    Sleeve,
)

EVENT_SYMBOL = "600519.SH"
TREND_SYMBOL = "300750.SZ"
FUND_SYMBOL = "601318.SH"


def synthetic_master() -> list[SecurityMasterRow]:
    return [
        SecurityMasterRow(
            symbol=EVENT_SYMBOL,
            name="贵州茅台",
            exchange="SH",
            board=Board.MAIN,
            list_date=date(2001, 8, 27),
            delist_date=None,
            status="listed",
            industry_code="801120",
            effective_from=date(2001, 8, 27),
            effective_to=None,
            median_amount_20d=4e9,
        ),
        SecurityMasterRow(
            symbol=TREND_SYMBOL,
            name="宁德时代",
            exchange="SZ",
            board=Board.CHINEXT,
            list_date=date(2018, 6, 11),
            delist_date=None,
            status="listed",
            industry_code="801730",
            effective_from=date(2018, 6, 11),
            effective_to=None,
            median_amount_20d=8e6,
        ),
        SecurityMasterRow(
            symbol=FUND_SYMBOL,
            name="中国平安",
            exchange="SH",
            board=Board.MAIN,
            list_date=date(2007, 3, 1),
            delist_date=None,
            status="listed",
            industry_code="801780",
            effective_from=date(2007, 3, 1),
            effective_to=None,
            median_amount_20d=2e9,
        ),
    ]


def mixed_candidates() -> list[Candidate]:
    return [
        Candidate(
            symbol=EVENT_SYMBOL,
            display_name="贵州茅台",
            sleeve=Sleeve.EVENT_CATALYST,
            horizon=Horizon.D5,
            state=CandidateState.WATCH,
            reason_code="not_yet_available",
            deterministic_score=0.81,
            invalidation_condition="次日开盘价已充分反映公告",
            valid_until=date(2026, 4, 24),
            factor_breakdown={"event_materiality": 0.9, "event_novelty": 0.7},
            evidence_ids=["syn-event-evening-announcement"],
            thesis_md="晚间公告在当日 source_cutoff 之后才可得，进入观察池。",
        ),
        Candidate(
            symbol=TREND_SYMBOL,
            display_name="宁德时代",
            sleeve=Sleeve.TREND_FLOW,
            horizon=Horizon.D20,
            state=CandidateState.WATCH,
            reason_code="liquidity_below_u2",
            deterministic_score=0.74,
            invalidation_condition="20 日中位成交额回升且相对强弱消失",
            valid_until=date(2026, 5, 15),
            factor_breakdown={"ret_20d": 0.8, "main_inflow_5d": 0.6},
            evidence_ids=["syn-trend-illiquid"],
            thesis_md="趋势分过线，但 20 日中位成交额低于 U2 流动性门槛。",
        ),
        Candidate(
            symbol=FUND_SYMBOL,
            display_name="中国平安",
            sleeve=Sleeve.FUNDAMENTAL_REVALUE,
            horizon=Horizon.D60,
            state=CandidateState.QUALIFIED,
            reason_code="passed_cost_and_liquidity",
            deterministic_score=0.69,
            rank=1,
            invalidation_condition="当期 ROE 回落或同业估值分位不再折价",
            valid_until=date(2026, 7, 10),
            factor_breakdown={"roe_trend": 0.7, "pb_peer_pct": 0.65},
            evidence_ids=["syn-fundamental-visible-fact"],
            thesis_md="当时已披露财务版本支持基本面重估，且满足可成交约束。",
        ),
    ]


def abstain_candidates() -> list[Candidate]:
    items = mixed_candidates()
    for item in items:
        item.state = CandidateState.WATCH
        item.rank = None
        if item.sleeve is Sleeve.FUNDAMENTAL_REVALUE:
            item.reason_code = "score_below_threshold"
            item.thesis_md = "基本面分未过资格线，现金为合法结果。"
    return items


SYNTHETIC_AS_OF = date(2026, 4, 10)
SYNTHETIC_CUTOFF = datetime(2026, 4, 10, 7, 30, tzinfo=UTC)
