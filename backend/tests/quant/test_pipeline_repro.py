"""合成流水线：三 sleeve 独立、可弃权、同版本重跑 hash 一致。"""

from datetime import UTC, datetime

from app.services.quant.contracts import CandidateState, RunVersions, Sleeve
from app.services.quant.recommendation.pipeline import run_synthetic_pipeline


def _versions() -> RunVersions:
    return RunVersions(
        dataset_version="synthetic-v0",
        factor_version="synthetic-v0",
        rule_version="cn-exchanges-2026-07-06",
        code_commit="phase0-test",
        config_snapshot={"max_symbol_weight": 0.08, "min_cash": 0.10},
        source_cutoff=datetime(2026, 4, 10, 7, 30, tzinfo=UTC),
    )


def test_abstain_scenario_returns_zero_qualified_with_reason() -> None:
    result = run_synthetic_pipeline(scenario="abstain", versions=_versions())
    assert result.qualified == []
    assert result.empty_reason == "no_positive_edge"
    assert result.empty_reason_detail
    assert all(item.state is not CandidateState.QUALIFIED for item in result.items)


def test_mixed_scenario_keeps_sleeves_independent() -> None:
    result = run_synthetic_pipeline(scenario="mixed", versions=_versions())
    by_sleeve = {item.sleeve: item for item in result.items}
    assert set(by_sleeve) == {
        Sleeve.EVENT_CATALYST,
        Sleeve.TREND_FLOW,
        Sleeve.FUNDAMENTAL_REVALUE,
    }
    assert by_sleeve[Sleeve.EVENT_CATALYST].state is CandidateState.WATCH
    assert by_sleeve[Sleeve.EVENT_CATALYST].reason_code == "not_yet_available"
    assert by_sleeve[Sleeve.TREND_FLOW].state is CandidateState.WATCH
    assert by_sleeve[Sleeve.TREND_FLOW].reason_code == "liquidity_below_u2"
    assert by_sleeve[Sleeve.FUNDAMENTAL_REVALUE].state is CandidateState.QUALIFIED
    assert len(result.qualified) == 1
    assert result.empty_reason is None


def test_same_versions_rerun_hash_is_stable() -> None:
    versions = _versions()
    first = run_synthetic_pipeline(scenario="mixed", versions=versions)
    second = run_synthetic_pipeline(scenario="mixed", versions=versions)
    assert first.result_hash == second.result_hash
    assert len(first.result_hash) == 64
