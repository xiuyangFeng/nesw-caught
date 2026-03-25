from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.research import EvaluationMetrics
from app.services.news_relevance_experiment_runner import (
    append_experiment_ledger_row,
    decide_experiment_outcome,
    ensure_allowed_paths,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one constrained market relevance experiment.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--baseline-id", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--changed-file", action="append", dest="changed_files", default=[])
    parser.add_argument("--metrics-before", type=Path, required=True, help="Path to baseline evaluation.json")
    parser.add_argument("--metrics-after", type=Path, required=True, help="Path to experiment evaluation.json")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--min-recall", type=float, default=0.4)
    args = parser.parse_args()

    changed_paths = [Path(path).resolve() for path in args.changed_files]
    ensure_allowed_paths(changed_paths)
    metrics_before = _load_metrics(args.metrics_before)
    metrics_after = _load_metrics(args.metrics_after)
    decision = decide_experiment_outcome(
        experiment_id=args.experiment_id,
        metrics_before=metrics_before,
        metrics_after=metrics_after,
        min_recall=args.min_recall,
    )
    append_experiment_ledger_row(
        args.ledger,
        baseline_id=args.baseline_id,
        hypothesis=args.hypothesis,
        changed_files=[str(path) for path in changed_paths],
        decision=decision,
    )
    print(decision.model_dump_json())


def _load_metrics(path: Path) -> EvaluationMetrics:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics", payload)
    return EvaluationMetrics.model_validate(metrics)


if __name__ == "__main__":
    main()
