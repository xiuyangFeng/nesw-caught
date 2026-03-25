from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.research import EvaluationMetrics
from app.services.news_relevance_experiment_runner import (
    ExperimentScopeError,
    append_experiment_ledger_row,
    decide_experiment_outcome,
    ensure_allowed_paths,
)


def test_experiment_runner_rejects_changes_outside_allowed_paths() -> None:
    with pytest.raises(ExperimentScopeError):
        ensure_allowed_paths(
            [
                Path("/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py"),
                Path("/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue"),
            ]
        )


def test_decide_experiment_outcome_rejects_precision_regression() -> None:
    decision = decide_experiment_outcome(
        experiment_id="exp-001",
        metrics_before=EvaluationMetrics(precision=0.62, recall=0.55, noise_rejection_rate=0.71),
        metrics_after=EvaluationMetrics(precision=0.6, recall=0.56, noise_rejection_rate=0.72),
        min_recall=0.4,
    )

    assert decision.decision == "reject"
    assert "precision" in decision.reason


def test_decide_experiment_outcome_rejects_noise_rejection_regression() -> None:
    decision = decide_experiment_outcome(
        experiment_id="exp-003",
        metrics_before=EvaluationMetrics(precision=0.62, recall=0.55, noise_rejection_rate=0.71),
        metrics_after=EvaluationMetrics(precision=0.64, recall=0.55, noise_rejection_rate=0.6),
        min_recall=0.4,
    )

    assert decision.decision == "reject"
    assert "noise_rejection_rate" in decision.reason


def test_append_experiment_ledger_row_writes_header_and_row(tmp_path) -> None:
    ledger_path = tmp_path / "experiments.tsv"
    decision = decide_experiment_outcome(
        experiment_id="exp-002",
        metrics_before=EvaluationMetrics(precision=0.62, recall=0.55, noise_rejection_rate=0.71),
        metrics_after=EvaluationMetrics(precision=0.66, recall=0.55, noise_rejection_rate=0.73),
        min_recall=0.4,
    )

    append_experiment_ledger_row(
        ledger_path,
        baseline_id="baseline-001",
        hypothesis="Tighten off-topic filter",
        changed_files=["backend/app/services/news_ingestion.py"],
        decision=decision,
    )

    content = ledger_path.read_text(encoding="utf-8").splitlines()
    assert content[0].startswith("experiment_id\tbaseline_id\thypothesis\tdecision")
    assert "exp-002" in content[1]
