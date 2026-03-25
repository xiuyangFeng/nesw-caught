from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.services.news_relevance_report import (
    build_market_relevance_report,
    render_market_relevance_report_html,
    render_market_relevance_report_markdown,
)


def _write_artifacts(tmp_path: Path) -> tuple[Path, Path, Path]:
    benchmark_path = tmp_path / "benchmark.jsonl"
    evaluation_path = tmp_path / "evaluation.json"
    ledger_path = tmp_path / "ledger.tsv"
    benchmark_rows = [
        {
            "sample_id": "fp-1",
            "source_type": "historical",
            "origin": {
                "news_id": 1,
                "source_name": "Reuters",
                "canonical_url": "https://example.com/fp-1",
                "published_at": "2026-03-25T00:00:00Z",
            },
            "content": {
                "title": "Generic capital increase",
                "summary": "A non-listed entity raised capital.",
                "body_excerpt": "",
            },
            "labels": {"market_relevant": False, "noise_type": "off_topic"},
            "annotation": {
                "label_source": "human_corrected",
                "model_name": "deepseek-chat",
                "confidence": 0.88,
                "review_notes": "Out of listed-equity scope.",
            },
        },
        {
            "sample_id": "fn-1",
            "source_type": "realtime",
            "origin": {
                "news_id": 2,
                "source_name": "CLS Telegraph",
                "canonical_url": "https://example.com/fn-1",
                "published_at": "2026-03-25T01:00:00Z",
            },
            "content": {
                "title": "沪指重返3900点上方",
                "summary": "日内涨超0.5%。",
                "body_excerpt": "",
            },
            "labels": {"market_relevant": True, "noise_type": None},
            "annotation": {
                "label_source": "human_reviewed",
                "model_name": "deepseek-chat",
                "confidence": 0.93,
                "review_notes": "Accepted.",
            },
        },
    ]
    benchmark_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in benchmark_rows) + "\n",
        encoding="utf-8",
    )
    evaluation_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "precision": 0.75,
                    "recall": 0.5,
                    "noise_rejection_rate": 0.9,
                },
                "false_positive_ids": ["fp-1"],
                "false_negative_ids": ["fn-1"],
                "sample_count": 2,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ledger_path.write_text(
        "\n".join(
            [
                "experiment_id\tbaseline_id\thypothesis\tdecision\treason\tchanged_files\ttimestamp",
                "baseline-001\tbaseline-001\tbaseline evaluation\tbaseline\tprecision=0.7500,recall=0.5000,noise_rejection_rate=0.9000\t\t2026-03-25T15:00:00Z",
                "exp-002\tbaseline-001\tCatch index spikes\tkeep\tprecision improved from 0.7500 to 0.8000\tbackend/app/services/news_relevance_evaluator.py\t2026-03-25T16:00:00Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return benchmark_path, evaluation_path, ledger_path


def test_build_market_relevance_report_aggregates_metrics_and_samples(tmp_path: Path) -> None:
    benchmark_path, evaluation_path, ledger_path = _write_artifacts(tmp_path)

    report = build_market_relevance_report(
        benchmark_path=benchmark_path,
        evaluation_path=evaluation_path,
        ledger_path=ledger_path,
    )

    assert report.metrics.precision == 0.75
    assert report.sample_count == 2
    assert report.benchmark_total == 2
    assert report.market_relevant_count == 1
    assert report.noise_count == 1
    assert report.false_positives[0].sample_id == "fp-1"
    assert report.false_positives[0].title == "Generic capital increase"
    assert report.false_negatives[0].sample_id == "fn-1"
    assert report.false_negatives[0].title == "沪指重返3900点上方"
    assert report.latest_ledger_entries[0].experiment_id == "exp-002"


def test_render_market_relevance_report_outputs_human_readable_sections(tmp_path: Path) -> None:
    benchmark_path, evaluation_path, ledger_path = _write_artifacts(tmp_path)
    report = build_market_relevance_report(
        benchmark_path=benchmark_path,
        evaluation_path=evaluation_path,
        ledger_path=ledger_path,
    )

    markdown = render_market_relevance_report_markdown(report)
    html = render_market_relevance_report_html(report)

    assert "# Market Relevance Morning Report" in markdown
    assert "precision: `0.7500`" in markdown
    assert "fp-1" in markdown
    assert "沪指重返3900点上方" in markdown
    assert "<title>Market Relevance Morning Report</title>" in html
    assert "Latest Metrics" in html
    assert "Catch index spikes" in html
    assert "False Negatives" in html


def test_render_market_relevance_report_script_writes_markdown_and_html(tmp_path: Path) -> None:
    benchmark_path, evaluation_path, ledger_path = _write_artifacts(tmp_path)
    markdown_output = tmp_path / "report.md"
    html_output = tmp_path / "report.html"

    result = subprocess.run(
        [
            sys.executable,
            "backend/scripts/render_market_relevance_report.py",
            "--benchmark",
            str(benchmark_path),
            "--evaluation",
            str(evaluation_path),
            "--ledger",
            str(ledger_path),
            "--markdown-output",
            str(markdown_output),
            "--html-output",
            str(html_output),
        ],
        cwd="/Users/xiuyang/Desktop/news-caught",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert markdown_output.exists()
    assert html_output.exists()
    assert "Market Relevance Morning Report" in markdown_output.read_text(encoding="utf-8")
    assert "<html" in html_output.read_text(encoding="utf-8")

