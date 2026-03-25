from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.news_relevance_dataset import (
    apply_reviewed_samples,
    select_review_samples,
    save_samples,
)
from app.services.news_relevance_annotation import _load_sample, _read_jsonl_lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Review and promote market relevance annotations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    select_parser = subparsers.add_parser("select", help="Export the next review queue from annotated candidates")
    select_parser.add_argument("candidates", type=Path, help="Path to annotated candidate JSONL file")
    select_parser.add_argument("output", type=Path, help="Path to write review queue JSONL")
    select_parser.add_argument("--confidence-threshold", type=float, default=0.75)
    select_parser.add_argument("--spot-check-count", type=int, default=10)
    select_parser.add_argument("--seed", type=int, default=0)

    apply_parser = subparsers.add_parser("apply", help="Apply reviewed queue back into candidates and benchmark")
    apply_parser.add_argument("candidates", type=Path, help="Path to annotated candidate JSONL file")
    apply_parser.add_argument("reviewed", type=Path, help="Path to reviewed queue JSONL file")
    apply_parser.add_argument("benchmark", type=Path, help="Path to benchmark JSONL file")
    args = parser.parse_args()

    if args.command == "select":
        samples = [_load_sample(line) for line in _read_jsonl_lines(args.candidates)]
        review_queue = select_review_samples(
            samples,
            low_confidence_threshold=args.confidence_threshold,
            spot_check_count_per_bucket=args.spot_check_count,
            rng_seed=args.seed,
        )
        save_samples(args.output, review_queue)
        print(f"selected {len(review_queue)} samples -> {args.output}")
        return

    promoted = apply_reviewed_samples(args.candidates, args.reviewed, args.benchmark)
    print(f"applied {promoted} reviewed samples -> {args.benchmark}")


if __name__ == "__main__":
    main()
