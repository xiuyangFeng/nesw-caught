"""确定性合成流水线：三 sleeve 独立打分，允许 0 条合格机会。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.quant.candidate import transition
from app.services.quant.contracts import (
    Candidate,
    CandidateState,
    PipelineResult,
    PipelineScenario,
    RunStatus,
    RunVersions,
    StageLog,
)
from app.services.quant.fixtures.synthetic import (
    abstain_candidates,
    mixed_candidates,
    synthetic_master,
)
from app.services.quant.universe import build_u2


def compute_result_hash(versions: RunVersions, items: list[Candidate]) -> str:
    payload = {
        "dataset_version": versions.dataset_version,
        "factor_version": versions.factor_version,
        "rule_version": versions.rule_version,
        "code_commit": versions.code_commit,
        "config_snapshot": versions.config_snapshot,
        "source_cutoff": versions.source_cutoff.isoformat(),
        "items": [
            {
                "symbol": item.symbol,
                "sleeve": item.sleeve.value,
                "horizon": item.horizon.value,
                "state": item.state.value,
                "reason_code": item.reason_code,
                "deterministic_score": item.deterministic_score,
                "rank": item.rank,
            }
            for item in sorted(items, key=lambda row: (row.sleeve.value, row.symbol))
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _stage(name: str, status: str, **detail: Any) -> StageLog:
    return StageLog(stage=name, status=status, detail=detail)


def _walk_to_state(item: Candidate) -> None:
    """用状态机校验夹具里的终态是合法路径，而不是直接写成 qualified。"""
    target = item.state
    state = CandidateState.DISCOVERED
    if target is CandidateState.DISCOVERED:
        return
    state = transition(state, CandidateState.VALIDATING, "synthetic_discovered")
    if target is CandidateState.VALIDATING:
        item.state = state
        return
    if target is CandidateState.WATCH:
        item.state = transition(state, CandidateState.WATCH, item.reason_code)
        return
    if target is CandidateState.QUALIFIED:
        item.state = transition(state, CandidateState.QUALIFIED, item.reason_code)
        return
    item.state = transition(state, target, item.reason_code)


def run_synthetic_pipeline(*, scenario: str, versions: RunVersions) -> PipelineResult:
    scenario_key = PipelineScenario(scenario)
    stages = [
        _stage("data_gate", "ok", coverage_pct=100, source="synthetic"),
        _stage("universe_u2", "ok", size=len(build_u2(synthetic_master(), versions.source_cutoff.date()))),
    ]

    raw_items = abstain_candidates() if scenario_key is PipelineScenario.ABSTAIN else mixed_candidates()
    for item in raw_items:
        _walk_to_state(item)
        stages.append(
            _stage(
                f"sleeve_{item.sleeve.value}",
                "ok",
                symbol=item.symbol,
                state=item.state.value,
                reason_code=item.reason_code,
            )
        )

    qualified = [item for item in raw_items if item.state is CandidateState.QUALIFIED]
    empty_reason = None
    empty_detail = None
    if not qualified:
        empty_reason = "no_positive_edge"
        empty_detail = "今日无正期望机会：阈值、流动性或信息可得时间未过线，现金为合法结果。"
    stages.append(
        _stage(
            "qualify",
            "ok",
            qualified_count=len(qualified),
            empty_reason=empty_reason,
        )
    )
    return PipelineResult(
        versions=versions,
        items=raw_items,
        qualified=qualified,
        empty_reason=empty_reason,
        empty_reason_detail=empty_detail,
        result_hash=compute_result_hash(versions, raw_items),
        stages=stages,
        status=RunStatus.OK,
    )
