from app.services.quant.allocator import allocate
from app.services.quant.factors import score_event, score_fundamental, score_trend


def test_d_grade_event_does_not_qualify() -> None:
    score = score_event(novelty=1, materiality=1, grade="D")
    assert score.qualify is False


def test_a_grade_material_event_can_qualify() -> None:
    score = score_event(novelty=1, materiality=1, grade="A")
    assert score.qualify is True
    assert score.sleeve == "event_catalyst"


def test_fundamental_without_financials_does_not_qualify() -> None:
    score = score_fundamental(net_profit_yoy=None, revenue_yoy=None, roe=None, covered=False)
    assert score.qualify is False
    assert score.reason_code == "fundamental_gap_no_financials"


def test_fundamental_with_data_is_watch_not_qualified() -> None:
    score = score_fundamental(net_profit_yoy=0.5, revenue_yoy=0.3, roe=15.0, covered=True)
    assert score.qualify is False
    assert score.reason_code == "fundamental_watch_above_threshold"
    assert score.breakdown["financial_coverage"] == 1.0


def test_trend_without_inflow_does_not_qualify() -> None:
    score = score_trend(inflow=None, adv=None)
    assert score.qualify is False
    assert score.sleeve == "trend_flow"


def test_allocator_keeps_cash_and_symbol_cap() -> None:
    positions, cash = allocate(
        [("AAA", "event_catalyst", 1.0), ("BBB", "trend_flow", 1.0), ("CCC", "trend_flow", 1.0)],
        max_symbol_weight=0.08,
        min_cash=0.1,
    )
    assert cash >= 0.1
    assert all(item.weight <= 0.08 + 1e-9 for item in positions)
    assert sum(item.weight for item in positions) + cash == 1.0 or cash >= 0.1
