from __future__ import annotations

from dataclasses import dataclass

from app.schemas.sentiment_eval import (
    SENTIMENT_LABELS,
    SentimentABComparison,
    SentimentModelRun,
)


@dataclass(frozen=True)
class SentimentConfusionHighlight:
    actual: str
    predicted: str
    count: int


@dataclass(frozen=True)
class SentimentReport:
    primary_model: str
    accuracy: float
    macro_f1: float
    sample_count: int
    per_label: list[dict[str, float | int | str]]
    top_confusions: list[SentimentConfusionHighlight]
    ab_winner: str | None
    ab_reason: str | None
    # 有 importance 标注样本时的加权准确率；数据集完全没有标注时为 None（不展示）。
    importance_weighted_accuracy: float | None = None


def build_sentiment_report(
    primary_run: SentimentModelRun,
    comparison: SentimentABComparison | None = None,
) -> SentimentReport:
    """把单模型指标（可选 A/B 对比）汇总成结构化报告。"""
    metrics = primary_run.metrics
    per_label = [
        {
            "label": row.label,
            "precision": row.precision,
            "recall": row.recall,
            "f1": row.f1,
            "support": row.support,
        }
        for row in metrics.per_label
    ]

    return SentimentReport(
        primary_model=primary_run.model_name,
        accuracy=metrics.accuracy,
        macro_f1=metrics.macro_f1,
        sample_count=metrics.sample_count,
        per_label=per_label,
        top_confusions=_top_confusions(metrics.confusion_matrix),
        ab_winner=comparison.winner if comparison else None,
        ab_reason=comparison.reason if comparison else None,
        importance_weighted_accuracy=metrics.importance_weighted_accuracy,
    )


def render_sentiment_report_markdown(report: SentimentReport) -> str:
    lines = [
        "# Sentiment Eval Report",
        "",
        "## Latest Metrics",
        "",
        f"- model: `{report.primary_model}`",
        f"- accuracy: `{report.accuracy:.4f}`",
        f"- macro_f1: `{report.macro_f1:.4f}`",
        f"- evaluated samples: `{report.sample_count}`",
    ]
    if report.importance_weighted_accuracy is not None:
        lines.append(f"- importance-weighted accuracy: `{report.importance_weighted_accuracy:.4f}`")
    lines += [
        "",
        "## Per-label P/R/F1",
        "",
        "| label | precision | recall | f1 | support |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report.per_label:
        lines.append(
            f"| {row['label']} | {float(row['precision']):.4f} | "
            f"{float(row['recall']):.4f} | {float(row['f1']):.4f} | {int(row['support'])} |"
        )

    lines.extend(["", "## Top Confusions", ""])
    if report.top_confusions:
        for highlight in report.top_confusions:
            lines.append(
                f"- 实际 `{highlight.actual}` → 预测 `{highlight.predicted}`：{highlight.count} 次"
            )
    else:
        lines.append("- (none)")

    if report.ab_winner:
        lines.extend(
            [
                "",
                "## A/B Decision",
                "",
                f"- winner: `{report.ab_winner}`",
                f"- reason: {report.ab_reason}",
            ]
        )
    return "\n".join(lines)


def _top_confusions(
    confusion_matrix: dict[str, dict[str, int]],
    *,
    limit: int = 3,
) -> list[SentimentConfusionHighlight]:
    highlights: list[SentimentConfusionHighlight] = []
    for actual in SENTIMENT_LABELS:
        row = confusion_matrix.get(actual, {})
        for predicted in SENTIMENT_LABELS:
            if actual == predicted:
                continue
            count = int(row.get(predicted, 0))
            if count > 0:
                highlights.append(
                    SentimentConfusionHighlight(actual=actual, predicted=predicted, count=count)
                )
    highlights.sort(key=lambda item: item.count, reverse=True)
    return highlights[:limit]
