from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.news_relevance_report import (
    build_market_relevance_report,
    render_market_relevance_report_html,
    render_market_relevance_report_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render market relevance morning report outputs.")
    parser.add_argument("--benchmark", type=Path, required=True, help="Path to benchmark JSONL file")
    parser.add_argument("--evaluation", type=Path, required=True, help="Path to evaluation JSON file")
    parser.add_argument("--ledger", type=Path, required=True, help="Path to experiment ledger TSV")
    parser.add_argument("--markdown-output", type=Path, required=True, help="Path to write Markdown report")
    parser.add_argument("--html-output", type=Path, required=True, help="Path to write HTML report")
    args = parser.parse_args()

    report = build_market_relevance_report(
        benchmark_path=args.benchmark,
        evaluation_path=args.evaluation,
        ledger_path=args.ledger,
    )
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_market_relevance_report_markdown(report), encoding="utf-8")
    args.html_output.write_text(render_market_relevance_report_html(report), encoding="utf-8")
    print(f"rendered report -> {args.markdown_output}, {args.html_output}")


if __name__ == "__main__":
    main()
