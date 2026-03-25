from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.services.news_relevance_annotation import annotate_market_relevance_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotate market relevance benchmark candidates.")
    parser.add_argument("input", type=Path, help="Path to candidate JSONL file")
    parser.add_argument("output", type=Path, help="Path to write annotated JSONL file")
    parser.add_argument("--batch-size", type=int, default=None, help="Flush output every N newly annotated samples")
    parser.add_argument("--resume", action="store_true", help="Reuse existing output rows and continue remaining samples")
    args = parser.parse_args()

    with SessionLocal() as session:
        annotated = annotate_market_relevance_file(
            args.input,
            args.output,
            session=session,
            batch_size=args.batch_size,
            resume=args.resume,
        )
    print(f"annotated {len(annotated)} samples -> {args.output}")


if __name__ == "__main__":
    main()
