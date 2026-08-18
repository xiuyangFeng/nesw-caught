from app.services.quant.candidate import InvalidTransitionError, transition
from app.services.quant.contracts import CandidateState
from app.services.quant.events import classify_event, evidence_grade
from app.services.quant.radar.ingest import propose_state


def test_cninfo_announcement_is_grade_a_hard_event() -> None:
    classified = classify_event(
        title="贵州茅台：2025 年年度报告",
        source_name="巨潮资讯网",
        source_url="https://www.cninfo.com.cn/new/disclosure/detail",
        summary="披露年报",
    )
    assert classified.evidence_grade == "A"
    assert classified.event_type == "periodic_report"


def test_social_rumor_is_grade_d() -> None:
    classified = classify_event(
        title="听说茅台要重组",
        source_name="雪球",
        source_url="https://xueqiu.com/123",
        summary="匿名传闻",
    )
    assert classified.evidence_grade == "D"
    assert evidence_grade("weibo", "https://weibo.com/x") == "D"


def test_d_grade_cannot_become_qualified() -> None:
    state = propose_state(
        evidence_grade="D",
        novelty=1.0,
        materiality=1.0,
        evidence_quality=0.2,
        reaction_gap=1.0,
    )
    assert state == CandidateState.DISCOVERED
    try:
        transition(CandidateState.DISCOVERED, CandidateState.QUALIFIED, "rumor")
        raise AssertionError("d-grade must not skip to qualified")
    except InvalidTransitionError:
        pass
