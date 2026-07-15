from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

from app.schemas.research import EvaluationMetrics
from app.services.news_relevance_dataset import load_benchmark_samples


@dataclass(frozen=True)
class ReportSampleEntry:
    sample_id: str
    title: str
    expected_market_relevant: bool | None
    noise_type: str | None


@dataclass(frozen=True)
class ReportLedgerEntry:
    experiment_id: str
    baseline_id: str
    hypothesis: str
    decision: str
    reason: str
    changed_files: str
    timestamp: str


@dataclass(frozen=True)
class MarketRelevanceReport:
    metrics: EvaluationMetrics
    sample_count: int
    benchmark_total: int
    market_relevant_count: int
    noise_count: int
    false_positives: list[ReportSampleEntry]
    false_negatives: list[ReportSampleEntry]
    latest_ledger_entries: list[ReportLedgerEntry]


def build_market_relevance_report(
    *,
    benchmark_path: str | Path,
    evaluation_path: str | Path,
    ledger_path: str | Path,
) -> MarketRelevanceReport:
    benchmark_samples = load_benchmark_samples(benchmark_path)
    by_id = {sample.sample_id: sample for sample in benchmark_samples}

    evaluation_payload = json.loads(Path(evaluation_path).read_text(encoding="utf-8"))
    metrics = EvaluationMetrics.model_validate(evaluation_payload["metrics"])
    sample_count = int(evaluation_payload["sample_count"])
    false_positive_ids = list(evaluation_payload.get("false_positive_ids", []))
    false_negative_ids = list(evaluation_payload.get("false_negative_ids", []))

    benchmark_total = len(benchmark_samples)
    market_relevant_count = sum(1 for sample in benchmark_samples if sample.labels.market_relevant)
    noise_count = benchmark_total - market_relevant_count

    return MarketRelevanceReport(
        metrics=metrics,
        sample_count=sample_count,
        benchmark_total=benchmark_total,
        market_relevant_count=market_relevant_count,
        noise_count=noise_count,
        false_positives=[_sample_entry(sample_id, by_id) for sample_id in false_positive_ids],
        false_negatives=[_sample_entry(sample_id, by_id) for sample_id in false_negative_ids],
        latest_ledger_entries=_load_ledger_entries(ledger_path)[:5],
    )


def render_market_relevance_report_markdown(report: MarketRelevanceReport) -> str:
    lines = [
        "# Market Relevance Morning Report",
        "",
        "## Latest Metrics",
        "",
        f"- precision: `{report.metrics.precision:.4f}`",
        f"- recall: `{report.metrics.recall:.4f}`",
        f"- noise_rejection_rate: `{report.metrics.noise_rejection_rate:.4f}`",
        f"- evaluated sample count: `{report.sample_count}`",
        "",
        "## Benchmark Snapshot",
        "",
        f"- total benchmark samples: `{report.benchmark_total}`",
        f"- market relevant: `{report.market_relevant_count}`",
        f"- noise samples: `{report.noise_count}`",
        "",
        "## False Positives",
        "",
    ]
    lines.extend(_markdown_sample_lines(report.false_positives))
    lines.extend(
        [
            "",
            "## False Negatives",
            "",
        ]
    )
    lines.extend(_markdown_sample_lines(report.false_negatives))
    lines.extend(
        [
            "",
            "## Recent Experiments",
            "",
        ]
    )
    for entry in report.latest_ledger_entries:
        lines.append(
            f"- `{entry.timestamp}` `{entry.experiment_id}` `{entry.decision}`: {entry.hypothesis} | {entry.reason}"
        )

    lines.extend(
        [
            "",
            "## Next Read",
            "",
            "- 优先看 false negatives，找当前规则漏掉的市场信号。",
            "- 如果 precision 开始下降，先回看最近一条 keep/reject 实验记录。",
        ]
    )
    return "\n".join(lines)


def render_market_relevance_report_html(report: MarketRelevanceReport) -> str:
    fp_cards = "".join(_html_sample_card(sample) for sample in report.false_positives) or "<p>(none)</p>"
    fn_cards = "".join(_html_sample_card(sample) for sample in report.false_negatives) or "<p>(none)</p>"
    ledger_rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(entry.timestamp)}</td>"
            f"<td>{html.escape(entry.experiment_id)}</td>"
            f"<td>{html.escape(entry.decision)}</td>"
            f"<td>{html.escape(entry.hypothesis)}</td>"
            f"<td>{html.escape(entry.reason)}</td>"
            "</tr>"
        )
        for entry in report.latest_ledger_entries
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Relevance Morning Report</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --card: #fffdf8;
      --ink: #1f1d19;
      --muted: #6f675b;
      --line: #ddd2bf;
      --accent: #8a4b2a;
      --accent-soft: #efe0d0;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Georgia, 'Times New Roman', serif; background: linear-gradient(180deg, #f7f2e9 0%, #efe5d5 100%); color: var(--ink); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    p {{ margin: 0; color: var(--muted); }}
    .hero {{ background: var(--card); border: 1px solid var(--line); border-radius: 20px; padding: 24px; box-shadow: 0 14px 40px rgba(71, 45, 22, 0.08); }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 20px; }}
    .metric, .panel {{ background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 18px; }}
    .metric strong {{ display: block; font-size: 28px; margin-bottom: 4px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 18px; }}
    .cards {{ display: grid; gap: 12px; }}
    .sample-card {{ border: 1px solid var(--line); border-radius: 12px; padding: 12px; background: #fffcf6; }}
    .sample-card .meta {{ color: var(--muted); font-size: 13px; margin-top: 6px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    .next {{ margin-top: 18px; background: var(--accent-soft); border-radius: 16px; padding: 16px; border: 1px solid #d8b89d; }}
    .eyebrow {{ text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); font-size: 12px; margin-bottom: 8px; }}
    @media (max-width: 860px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="eyebrow">Autoresearch Morning Read</div>
      <h1>Market Relevance Morning Report</h1>
      <p>Open this first to see current benchmark health, missed signals, and the latest experiment trail.</p>
      <h2 style="margin-top: 20px;">Latest Metrics</h2>
      <div class="metrics">
        <div class="metric"><strong>{report.metrics.precision:.4f}</strong><span>Precision</span></div>
        <div class="metric"><strong>{report.metrics.recall:.4f}</strong><span>Recall</span></div>
        <div class="metric"><strong>{report.metrics.noise_rejection_rate:.4f}</strong><span>Noise Rejection</span></div>
        <div class="metric"><strong>{report.sample_count}</strong><span>Evaluated Samples</span></div>
      </div>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>Benchmark Snapshot</h2>
        <div class="metrics">
          <div class="metric"><strong>{report.benchmark_total}</strong><span>Total</span></div>
          <div class="metric"><strong>{report.market_relevant_count}</strong><span>Relevant</span></div>
          <div class="metric"><strong>{report.noise_count}</strong><span>Noise</span></div>
        </div>
      </div>
      <div class="panel next">
        <h2>Next Read</h2>
        <p>Prioritize false negatives first. If precision slips, compare against the latest kept or rejected experiment before changing rules again.</p>
      </div>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>False Positives</h2>
        <div class="cards">{fp_cards}</div>
      </div>
      <div class="panel">
        <h2>False Negatives</h2>
        <div class="cards">{fn_cards}</div>
      </div>
    </section>
    <section class="panel" style="margin-top: 18px;">
      <h2>Recent Experiments</h2>
      <table>
        <thead>
          <tr><th>Timestamp</th><th>ID</th><th>Decision</th><th>Hypothesis</th><th>Reason</th></tr>
        </thead>
        <tbody>{ledger_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""


def _sample_entry(sample_id: str, by_id: dict[str, object]) -> ReportSampleEntry:
    sample = by_id.get(sample_id)
    if sample is None:
        return ReportSampleEntry(
            sample_id=sample_id,
            title="(missing from benchmark)",
            expected_market_relevant=None,
            noise_type=None,
        )
    return ReportSampleEntry(
        sample_id=sample.sample_id,
        title=sample.content.title,
        expected_market_relevant=sample.labels.market_relevant,
        noise_type=sample.labels.noise_type,
    )


def _load_ledger_entries(path: str | Path) -> list[ReportLedgerEntry]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    entries: list[ReportLedgerEntry] = []
    for row in lines[1:]:
        if not row.strip():
            continue
        columns = row.split("\t")
        if len(columns) < 7:
            continue
        entries.append(
            ReportLedgerEntry(
                experiment_id=columns[0],
                baseline_id=columns[1],
                hypothesis=columns[2],
                decision=columns[3],
                reason=columns[4],
                changed_files=columns[5],
                timestamp=columns[6],
            )
        )
    return list(reversed(entries))


def _markdown_sample_lines(samples: list[ReportSampleEntry]) -> list[str]:
    if not samples:
        return ["- (none)"]
    lines: list[str] = []
    for sample in samples:
        label = (
            "relevant"
            if sample.expected_market_relevant is True
            else f"not relevant ({sample.noise_type})"
            if sample.expected_market_relevant is False
            else "missing"
        )
        lines.append(f"- `{sample.sample_id}` {sample.title} | expected: {label}")
    return lines


def _html_sample_card(sample: ReportSampleEntry) -> str:
    label = (
        "relevant"
        if sample.expected_market_relevant is True
        else f"not relevant ({sample.noise_type})"
        if sample.expected_market_relevant is False
        else "missing"
    )
    return (
        "<article class=\"sample-card\">"
        f"<strong>{html.escape(sample.sample_id)}</strong>"
        f"<div>{html.escape(sample.title)}</div>"
        f"<div class=\"meta\">expected: {html.escape(label)}</div>"
        "</article>"
    )
