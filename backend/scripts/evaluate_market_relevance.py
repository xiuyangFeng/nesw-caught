from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.services.news_relevance_dataset import load_benchmark_samples
from app.services.news_relevance_evaluator import evaluate_market_relevance, predict_market_relevance_batch
from app.services.news_relevance_experiment_runner import append_baseline_ledger_row


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate market relevance benchmark results.")
    parser.add_argument("--dataset", type=Path, required=True, help="Path to benchmark JSONL file")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for evaluation artifacts")
    parser.add_argument("--min-recall", type=float, default=0.4, help="Minimum acceptable recall")
    parser.add_argument("--ledger", type=Path, default=None, help="Optional ledger TSV path for baseline capture")
    parser.add_argument("--experiment-id", default=None, help="Ledger experiment id when appending baseline")
    args = parser.parse_args()

    with SessionLocal() as session:
        samples = predict_market_relevance_batch(load_benchmark_samples(args.dataset), session=session)
    result = evaluate_market_relevance(samples, min_recall=args.min_recall)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "metrics": result.metrics.model_dump(),
        "false_positive_ids": result.false_positive_ids,
        "false_negative_ids": result.false_negative_ids,
        "sample_count": len(samples),
    }
    (args.output_dir / "evaluation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "evaluation.md").write_text(
        "\n".join(
            [
                "# Market Relevance Evaluation",
                "",
                f"- precision: {result.metrics.precision:.4f}",
                f"- recall: {result.metrics.recall:.4f}",
                f"- noise_rejection_rate: {result.metrics.noise_rejection_rate:.4f}",
                f"- false_positive_ids: {', '.join(result.false_positive_ids) or '(none)'}",
                f"- false_negative_ids: {', '.join(result.false_negative_ids) or '(none)'}",
            ]
        ),
        encoding="utf-8",
    )
    if args.ledger is not None:
        experiment_id = args.experiment_id or datetime.now(timezone.utc).strftime("baseline-%Y%m%dT%H%M%SZ")
        append_baseline_ledger_row(
            args.ledger,
            experiment_id=experiment_id,
            metrics=result.metrics,
            dataset_path=str(args.dataset),
            artifact_dir=str(args.output_dir),
        )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
