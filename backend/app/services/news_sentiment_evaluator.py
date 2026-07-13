from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from app.schemas.sentiment_eval import SENTIMENT_LABELS, SentimentGoldSample

# 与 schema 保持同一份标签集合。
LABELS: tuple[str, ...] = SENTIMENT_LABELS


class SentimentEvaluationError(ValueError):
    pass


@dataclass(frozen=True)
class SentimentLabelScore:
    label: str
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class SentimentEvaluationResult:
    accuracy: float
    macro_f1: float
    sample_count: int
    per_label: dict[str, SentimentLabelScore]
    # confusion_matrix[actual][predicted] = 计数
    confusion_matrix: dict[str, dict[str, int]]


def evaluate_sentiment(
    gold_labels: Sequence[str],
    predicted_labels: Sequence[str],
) -> SentimentEvaluationResult:
    """对齐的金标/预测标签列表 → per-label precision/recall/F1 + 混淆矩阵 + 准确率。"""
    if len(gold_labels) != len(predicted_labels):
        raise SentimentEvaluationError(
            f"gold/predicted length mismatch: {len(gold_labels)} vs {len(predicted_labels)}"
        )
    if not gold_labels:
        raise SentimentEvaluationError("cannot evaluate an empty dataset")

    confusion: dict[str, dict[str, int]] = {
        actual: {predicted: 0 for predicted in LABELS} for actual in LABELS
    }
    correct = 0
    for gold, predicted in zip(gold_labels, predicted_labels):
        if gold not in LABELS:
            raise SentimentEvaluationError(f"unknown gold label: {gold}")
        if predicted not in LABELS:
            raise SentimentEvaluationError(f"unknown predicted label: {predicted}")
        confusion[gold][predicted] += 1
        if gold == predicted:
            correct += 1

    total = len(gold_labels)
    per_label: dict[str, SentimentLabelScore] = {}
    f1_values: list[float] = []
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[actual][label] for actual in LABELS if actual != label)
        support = sum(confusion[label].values())
        fn = support - tp
        precision = _safe_divide(tp, tp + fp)
        recall = _safe_divide(tp, tp + fn)
        f1 = _safe_divide(2 * precision * recall, precision + recall)
        per_label[label] = SentimentLabelScore(
            label=label,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            support=support,
        )
        f1_values.append(f1)

    accuracy = _safe_divide(correct, total)
    macro_f1 = _safe_divide(sum(f1_values), len(f1_values))

    return SentimentEvaluationResult(
        accuracy=round(accuracy, 4),
        macro_f1=round(macro_f1, 4),
        sample_count=total,
        per_label=per_label,
        confusion_matrix=confusion,
    )


def evaluate_sentiment_samples(samples: Sequence[SentimentGoldSample]) -> SentimentEvaluationResult:
    """样本已带 predicted_sentiment 时的便捷入口，缺预测则报错。"""
    gold: list[str] = []
    predicted: list[str] = []
    for sample in samples:
        if sample.predicted_sentiment is None:
            raise SentimentEvaluationError(
                f"sample {sample.sample_id} is missing predicted_sentiment"
            )
        gold.append(sample.sentiment_label)
        predicted.append(sample.predicted_sentiment)
    return evaluate_sentiment(gold, predicted)


def build_rule_sentiment_classifier(
    classifier: object,
    *,
    positive_threshold: float = 0.2,
    negative_threshold: float = -0.2,
) -> Callable[[str], str]:
    """把一个带 classify(...) 的分类器包成 text -> label 的函数。

    通过可调阈值切分 sentiment_score，方便对同一分类器做不同配置的 A/B。
    分类器需暴露 classify(title=, summary=, body=, allow_llm=) -> 带 sentiment_score
    的结果对象（news_signal_classifier.NewsSignalClassifier 即满足）。
    """

    def classify(text: str) -> str:
        result = classifier.classify(title=text, summary=None, body=None, allow_llm=False)
        score = getattr(result, "sentiment_score", 0.0)
        if score >= positive_threshold:
            return "positive"
        if score <= negative_threshold:
            return "negative"
        return "neutral"

    return classify


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
