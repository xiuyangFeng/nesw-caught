from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.news_relevance_dataset import load_benchmark_samples
from app.services.news_relevance_evaluator import evaluate_market_relevance, predict_market_relevance


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate market relevance benchmark results.")
    parser.add_argument("--dataset", type=Path, required=True, help="Path to benchmark JSONL file")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for evaluation artifacts")
    parser.add_argument("--min-recall", type=float, default=0.4, help="Minimum acceptable recall")
    args = parser.parse_args()

    samples = [
        sample.model_copy(update={"predicted_market_relevant": predict_market_relevance(sample)})
        for sample in load_benchmark_samples(args.dataset)
    ]
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
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
