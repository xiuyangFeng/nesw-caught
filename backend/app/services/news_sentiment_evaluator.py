from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

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
    for gold, predicted in zip(gold_labels, predicted_labels, strict=True):
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
) -> Callable[[SentimentGoldSample], str]:
    """把一个带 classify(...) 的分类器包成 sample -> label 的函数（离线规则评测，allow_llm=False）。

    通过可调阈值切分 sentiment_score，方便对同一分类器做不同配置的 A/B。
    输入与线上分类路径对齐：title=sample.effective_title、summary=sample.summary、
    body=sample.body。分类器需暴露 classify(title=, summary=, body=, allow_llm=) ->
    带 sentiment_score 的结果对象（news_signal_classifier.NewsSignalClassifier 即满足）。

    注：NewsSignalClassifier.classify 当前不接受 market 参数，因此 sample.market
    这里无法透传（工作块 A 未扩展该签名，本工作块也不改动 news_signal_classifier.py）；
    中英词典路径仍由标题/摘要/正文内容本身决定。
    """

    def classify(sample: SentimentGoldSample) -> str:
        result = classifier.classify(
            title=sample.effective_title,
            summary=sample.summary,
            body=sample.body,
            allow_llm=False,
        )
        score = getattr(result, "sentiment_score", 0.0)
        if score >= positive_threshold:
            return "positive"
        if score <= negative_threshold:
            return "negative"
        return "neutral"

    return classify


def build_hybrid_sentiment_classifier(classifier: object) -> Callable[[SentimentGoldSample], str]:
    """生产路径的 sample -> label 包装：classify(allow_llm=True)，置信度不足时走 LLM 精修。

    与 build_rule_sentiment_classifier 同源输入对齐规则，唯一差异是 allow_llm=True，
    对应 POST /sentiment/run 里的 `hybrid:<provider>/<model>` run。
    """

    def classify(sample: SentimentGoldSample) -> str:
        result = classifier.classify(
            title=sample.effective_title,
            summary=sample.summary,
            body=sample.body,
            allow_llm=True,
        )
        return result.sentiment_label

    return classify


def compute_importance_weighted_accuracy(
    samples: Sequence[SentimentGoldSample],
    predicted_labels: Sequence[str],
) -> float | None:
    """按 sample.importance 加权的准确率；无标注样本权重按 1.0 计。

    数据集内所有样本都没有 importance 标注时返回 None（没有额外信息量，
    与未加权 accuracy 完全等价，不必重复展示）。
    """
    if not samples:
        return None
    if not any(sample.importance is not None for sample in samples):
        return None

    total_weight = 0.0
    correct_weight = 0.0
    for sample, predicted in zip(samples, predicted_labels, strict=True):
        weight = sample.importance if sample.importance is not None else 1.0
        total_weight += weight
        if sample.sentiment_label == predicted:
            correct_weight += weight

    # 全部样本显式标注 importance=0 时权重和为 0：加权准确率不可计算，
    # 返回 None 而不是误呈现为 0。
    if total_weight <= 0.0:
        return None
    return round(correct_weight / total_weight, 4)


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
