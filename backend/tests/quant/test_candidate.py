"""候选状态机：禁止把 discovered 直接当成 qualified，每次迁移必须带原因。"""

import pytest

from app.services.quant.candidate import InvalidTransitionError, transition
from app.services.quant.contracts import CandidateState


def test_happy_path_requires_reason_codes() -> None:
    state = CandidateState.DISCOVERED
    state = transition(state, CandidateState.VALIDATING, "rule_hit")
    state = transition(state, CandidateState.WATCH, "edge_below_threshold")
    state = transition(state, CandidateState.QUALIFIED, "passed_cost_and_liquidity")
    assert state is CandidateState.QUALIFIED


def test_discovered_cannot_skip_to_qualified() -> None:
    with pytest.raises(InvalidTransitionError):
        transition(CandidateState.DISCOVERED, CandidateState.QUALIFIED, "looks_good")


def test_blank_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="reason_code"):
        transition(CandidateState.DISCOVERED, CandidateState.VALIDATING, "")
