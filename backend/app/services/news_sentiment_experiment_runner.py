from __future__ import annotations

from collections.abc import Callable, Sequence

from app.schemas.sentiment_eval import (
    SENTIMENT_LABELS,
    SentimentABComparison,
    SentimentEvaluationMetrics,
    SentimentGoldSample,
    SentimentLabelDelta,
    SentimentLabelMetrics,
    SentimentModelRun,
)
from app.services.news_sentiment_evaluator import (
    SentimentEvaluationError,
    SentimentEvaluationResult,
    compute_importance_weighted_accuracy,
    evaluate_sentiment,
)

# sample -> sentiment_label（可注入 mock，实现离线可测）。
# 接收完整 SentimentGoldSample 而非纯文本，是为了让注入的分类函数能拿到
# title/summary/body/market 等与线上分类输入对齐的字段（情绪评测重构 Phase 1
# 工作块 B：评测输入对齐）。
ClassifyFn = Callable[[SentimentGoldSample], str]


def run_sentiment_evaluation(
    samples: Sequence[SentimentGoldSample],
    *,
    model_name: str,
    classify_fn: ClassifyFn,
) -> SentimentModelRun:
    """用注入的分类函数跑一遍评测，返回带指标的单模型结果。"""
    if not samples:
        raise SentimentEvaluationError("cannot evaluate an empty dataset")

    gold = [sample.sentiment_label for sample in samples]
    predicted = [classify_fn(sample) for sample in samples]
    result = evaluate_sentiment(gold, predicted)
    weighted_accuracy = compute_importance_weighted_accuracy(samples, predicted)
    return SentimentModelRun(model_name=model_name, metrics=_to_metrics(result, weighted_accuracy))


def compare_sentiment_runs(
    run_a: SentimentModelRun,
    run_b: SentimentModelRun,
) -> SentimentABComparison:
    """对两次模型运行做 A/B 对比：准确率、macro-F1、逐标签 F1 差值与胜者。"""
    f1_before = {row.label: row.f1 for row in run_a.metrics.per_label}
    f1_after = {row.label: row.f1 for row in run_b.metrics.per_label}

    label_deltas: list[SentimentLabelDelta] = []
    for label in SENTIMENT_LABELS:
        before = f1_before.get(label, 0.0)
        after = f1_after.get(label, 0.0)
        label_deltas.append(
            SentimentLabelDelta(
                label=label,
                f1_before=before,
                f1_after=after,
                f1_delta=round(after - before, 4),
            )
        )

    accuracy_delta = round(run_b.metrics.accuracy - run_a.metrics.accuracy, 4)
    macro_f1_delta = round(run_b.metrics.macro_f1 - run_a.metrics.macro_f1, 4)

    if macro_f1_delta > 0:
        winner = "model_b"
        reason = (
            f"{run_b.model_name} macro-F1 提升 {macro_f1_delta:+.4f}"
            f"（{run_a.metrics.macro_f1:.4f} → {run_b.metrics.macro_f1:.4f}）"
        )
    elif macro_f1_delta < 0:
        winner = "model_a"
        reason = (
            f"{run_b.model_name} macro-F1 回退 {macro_f1_delta:+.4f}"
            f"（{run_a.metrics.macro_f1:.4f} → {run_b.metrics.macro_f1:.4f}），保留 {run_a.model_name}"
        )
    else:
        winner = "tie"
        reason = f"两套配置 macro-F1 持平（{run_a.metrics.macro_f1:.4f}）"

    return SentimentABComparison(
        model_a=run_a,
        model_b=run_b,
        accuracy_delta=accuracy_delta,
        macro_f1_delta=macro_f1_delta,
        label_deltas=label_deltas,
        winner=winner,
        reason=reason,
    )


def run_sentiment_ab(
    samples: Sequence[SentimentGoldSample],
    *,
    model_a_name: str,
    model_a_classify: ClassifyFn,
    model_b_name: str,
    model_b_classify: ClassifyFn,
) -> SentimentABComparison:
    """对同一金标集用两套配置各评一遍并对比（A/B）。"""
    run_a = run_sentiment_evaluation(samples, model_name=model_a_name, classify_fn=model_a_classify)
    run_b = run_sentiment_evaluation(samples, model_name=model_b_name, classify_fn=model_b_classify)
    return compare_sentiment_runs(run_a, run_b)


def _to_metrics(
    result: SentimentEvaluationResult,
    importance_weighted_accuracy: float | None = None,
) -> SentimentEvaluationMetrics:
    return SentimentEvaluationMetrics(
        accuracy=result.accuracy,
        macro_f1=result.macro_f1,
        sample_count=result.sample_count,
        per_label=[
            SentimentLabelMetrics(
                label=score.label,
                precision=score.precision,
                recall=score.recall,
                f1=score.f1,
                support=score.support,
            )
            for score in result.per_label.values()
        ],
        confusion_matrix=result.confusion_matrix,
        importance_weighted_accuracy=importance_weighted_accuracy,
    )
