from __future__ import annotations

import argparse
from pathlib import Path

from app.services.news_relevance_dataset import merge_reviewed_samples


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote reviewed market relevance samples into the benchmark set.")
    parser.add_argument("candidates", type=Path, help="Path to annotated candidate JSONL file")
    parser.add_argument("benchmark", type=Path, help="Path to benchmark JSONL file")
    args = parser.parse_args()

    promoted = merge_reviewed_samples(args.candidates, args.benchmark)
    print(f"promoted {promoted} reviewed samples -> {args.benchmark}")


if __name__ == "__main__":
    main()
