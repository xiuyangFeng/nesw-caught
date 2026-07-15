from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.news_relevance_annotation import _load_sample, _read_jsonl_lines
from app.services.news_relevance_dataset import (
    apply_reviewed_samples,
    export_review_samples_csv,
    export_review_samples_markdown,
    import_review_decisions_csv,
    save_samples,
    select_review_samples,
)


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

    export_parser = subparsers.add_parser("export", help="Export review queue to a readable Markdown file")
    export_parser.add_argument("review_queue", type=Path, help="Path to review queue JSONL file")
    export_parser.add_argument("output", type=Path, help="Path to write Markdown export")

    export_csv_parser = subparsers.add_parser("export-csv", help="Export review queue to an editable CSV file")
    export_csv_parser.add_argument("review_queue", type=Path, help="Path to review queue JSONL file")
    export_csv_parser.add_argument("output", type=Path, help="Path to write CSV export")

    import_csv_parser = subparsers.add_parser("import-csv", help="Import reviewed CSV decisions back to JSONL")
    import_csv_parser.add_argument("review_queue", type=Path, help="Path to original review queue JSONL file")
    import_csv_parser.add_argument("review_csv", type=Path, help="Path to edited review CSV file")
    import_csv_parser.add_argument("output", type=Path, help="Path to write reviewed queue JSONL file")
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

    if args.command == "export":
        samples = [_load_sample(line) for line in _read_jsonl_lines(args.review_queue)]
        args.output.write_text(export_review_samples_markdown(samples), encoding="utf-8")
        print(f"exported {len(samples)} samples -> {args.output}")
        return

    if args.command == "export-csv":
        samples = [_load_sample(line) for line in _read_jsonl_lines(args.review_queue)]
        args.output.write_text(export_review_samples_csv(samples), encoding="utf-8", newline="")
        print(f"exported {len(samples)} samples -> {args.output}")
        return

    if args.command == "import-csv":
        imported = import_review_decisions_csv(args.review_queue, args.review_csv, args.output)
        print(f"imported {len(imported)} samples -> {args.output}")
        return

    promoted = apply_reviewed_samples(args.candidates, args.reviewed, args.benchmark)
    print(f"applied {promoted} reviewed samples -> {args.benchmark}")


if __name__ == "__main__":
    main()
