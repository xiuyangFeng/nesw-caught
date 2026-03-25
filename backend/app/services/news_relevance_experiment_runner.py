from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.schemas.research import EvaluationMetrics, ExperimentDecision

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALLOWED_PREFIXES = (
    _REPO_ROOT / "backend/app/services/news_ingestion.py",
    _REPO_ROOT / "backend/app/services/news_signal_pipeline.py",
    _REPO_ROOT / "backend/app/services/news_signal_classifier.py",
    _REPO_ROOT / "backend/data",
)


class ExperimentScopeError(ValueError):
    pass


def ensure_allowed_paths(paths: list[Path]) -> None:
    for path in paths:
        resolved = path.resolve()
        if not any(_is_relative_to(resolved, allowed) for allowed in _ALLOWED_PREFIXES):
            raise ExperimentScopeError(f"path is outside allowed scope: {resolved}")


def decide_experiment_outcome(
    *,
    experiment_id: str,
    metrics_before: EvaluationMetrics,
    metrics_after: EvaluationMetrics,
    min_recall: float,
) -> ExperimentDecision:
    if metrics_after.recall < min_recall:
        return ExperimentDecision(
            experiment_id=experiment_id,
            decision="reject",
            reason=f"recall {metrics_after.recall:.4f} fell below guardrail {min_recall:.4f}",
            metrics_before=metrics_before,
            metrics_after=metrics_after,
        )
    if metrics_after.precision < metrics_before.precision:
        return ExperimentDecision(
            experiment_id=experiment_id,
            decision="reject",
            reason=(
                f"precision regressed from {metrics_before.precision:.4f} "
                f"to {metrics_after.precision:.4f}"
            ),
            metrics_before=metrics_before,
            metrics_after=metrics_after,
        )
    if metrics_after.noise_rejection_rate < metrics_before.noise_rejection_rate:
        return ExperimentDecision(
            experiment_id=experiment_id,
            decision="reject",
            reason=(
                "noise_rejection_rate regressed from "
                f"{metrics_before.noise_rejection_rate:.4f} to {metrics_after.noise_rejection_rate:.4f}"
            ),
            metrics_before=metrics_before,
            metrics_after=metrics_after,
        )
    decision = "keep" if metrics_after.precision > metrics_before.precision else "reject"
    reason = (
        f"precision improved from {metrics_before.precision:.4f} to {metrics_after.precision:.4f}"
        if decision == "keep"
        else "metrics did not improve over baseline"
    )
    return ExperimentDecision(
        experiment_id=experiment_id,
        decision=decision,
        reason=reason,
        metrics_before=metrics_before,
        metrics_after=metrics_after,
    )


def append_experiment_ledger_row(
    ledger_path: str | Path,
    *,
    baseline_id: str,
    hypothesis: str,
    changed_files: list[str],
    decision: ExperimentDecision,
) -> None:
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "experiment_id\tbaseline_id\thypothesis\tdecision\treason\tchanged_files\ttimestamp\n",
            encoding="utf-8",
        )

    row = "\t".join(
        [
            decision.experiment_id,
            baseline_id,
            hypothesis.replace("\t", " ").strip(),
            decision.decision,
            decision.reason.replace("\t", " ").strip(),
            ",".join(changed_files),
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        ]
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(row)
        handle.write("\n")


def _is_relative_to(path: Path, candidate: Path) -> bool:
    try:
        path.relative_to(candidate)
        return True
    except ValueError:
        return path == candidate
