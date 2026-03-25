from __future__ import annotations

import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.services.news_relevance_annotation import annotate_market_relevance_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotate market relevance benchmark candidates.")
    parser.add_argument("input", type=Path, help="Path to candidate JSONL file")
    parser.add_argument("output", type=Path, help="Path to write annotated JSONL file")
    args = parser.parse_args()

    with SessionLocal() as session:
        annotated = annotate_market_relevance_file(args.input, args.output, session=session)
    print(f"annotated {len(annotated)} samples -> {args.output}")


if __name__ == "__main__":
    main()
