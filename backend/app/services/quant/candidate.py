"""候选状态机。发现不等于推荐；每次迁移必须带原因码。"""

from __future__ import annotations

from app.services.quant.contracts import CandidateState

ALLOWED_TRANSITIONS: dict[CandidateState, frozenset[CandidateState]] = {
    CandidateState.DISCOVERED: frozenset(
        {CandidateState.VALIDATING, CandidateState.INVALIDATED, CandidateState.EXPIRED}
    ),
    CandidateState.VALIDATING: frozenset(
        {
            CandidateState.WATCH,
            CandidateState.QUALIFIED,
            CandidateState.INVALIDATED,
            CandidateState.EXPIRED,
        }
    ),
    CandidateState.WATCH: frozenset(
        {CandidateState.QUALIFIED, CandidateState.INVALIDATED, CandidateState.EXPIRED}
    ),
    CandidateState.QUALIFIED: frozenset({CandidateState.INVALIDATED, CandidateState.EXPIRED}),
    CandidateState.INVALIDATED: frozenset(),
    CandidateState.EXPIRED: frozenset(),
}


class InvalidTransitionError(ValueError):
    """不允许的状态跳转。"""


def transition(state: CandidateState, target: CandidateState, reason_code: str) -> CandidateState:
    if not reason_code.strip():
        raise ValueError("reason_code is required for every candidate transition")
    allowed = ALLOWED_TRANSITIONS[state]
    if target not in allowed:
        raise InvalidTransitionError(f"cannot move from {state} to {target}")
    return target
