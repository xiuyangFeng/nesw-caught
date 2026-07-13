from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.schemas.sentiment_eval import SentimentGoldSample
from app.services.news_sentiment_evaluator import (
    SentimentEvaluationError,
    build_rule_sentiment_classifier,
    evaluate_sentiment,
    evaluate_sentiment_samples,
)


def test_evaluate_sentiment_reports_per_label_metrics_and_confusion_matrix() -> None:
    gold = ["positive", "positive", "negative", "neutral"]
    predicted = ["positive", "negative", "negative", "neutral"]

    result = evaluate_sentiment(gold, predicted)

    # 3/4 命中
    assert result.accuracy == 0.75
    assert result.sample_count == 4

    # 混淆矩阵 actual -> predicted
    assert result.confusion_matrix["positive"] == {"positive": 1, "negative": 1, "neutral": 0}
    assert result.confusion_matrix["negative"] == {"positive": 0, "negative": 1, "neutral": 0}
    assert result.confusion_matrix["neutral"] == {"positive": 0, "negative": 0, "neutral": 1}

    positive = result.per_label["positive"]
    assert positive.precision == 1.0
    assert positive.recall == 0.5
    assert positive.f1 == 0.6667
    assert positive.support == 2

    negative = result.per_label["negative"]
    assert negative.precision == 0.5
    assert negative.recall == 1.0
    assert negative.f1 == 0.6667
    assert negative.support == 1

    neutral = result.per_label["neutral"]
    assert neutral.precision == 1.0
    assert neutral.recall == 1.0
    assert neutral.f1 == 1.0

    assert result.macro_f1 == 0.7778


def test_evaluate_sentiment_perfect_predictions() -> None:
    gold = ["positive", "negative", "neutral"]
    result = evaluate_sentiment(gold, list(gold))

    assert result.accuracy == 1.0
    assert result.macro_f1 == 1.0
    for label in ("positive", "negative", "neutral"):
        assert result.per_label[label].f1 == 1.0


def test_evaluate_sentiment_rejects_length_mismatch() -> None:
    with pytest.raises(SentimentEvaluationError):
        evaluate_sentiment(["positive", "negative"], ["positive"])


def test_evaluate_sentiment_rejects_empty_dataset() -> None:
    with pytest.raises(SentimentEvaluationError):
        evaluate_sentiment([], [])


def test_evaluate_sentiment_rejects_unknown_label() -> None:
    with pytest.raises(SentimentEvaluationError):
        evaluate_sentiment(["positive"], ["bullish"])


def _sample(sample_id: str, gold: str, predicted: str | None) -> SentimentGoldSample:
    return SentimentGoldSample(
        sample_id=sample_id,
        text=f"text for {sample_id}",
        sentiment_label=gold,
        predicted_sentiment=predicted,
    )


def test_evaluate_sentiment_samples_uses_predicted_field() -> None:
    samples = [
        _sample("s1", "positive", "positive"),
        _sample("s2", "negative", "neutral"),
    ]
    result = evaluate_sentiment_samples(samples)

    assert result.sample_count == 2
    assert result.accuracy == 0.5


def test_evaluate_sentiment_samples_requires_predictions() -> None:
    samples = [_sample("s1", "positive", None)]
    with pytest.raises(SentimentEvaluationError) as exc:
        evaluate_sentiment_samples(samples)
    assert "predicted_sentiment" in str(exc.value)


@dataclass
class _FakeClassificationResult:
    sentiment_score: float


class _FakeClassifier:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores

    def classify(self, *, title: str, summary, body, allow_llm: bool = True):
        assert allow_llm is False  # 评测必须离线
        return _FakeClassificationResult(sentiment_score=self.scores[title])


def test_build_rule_sentiment_classifier_applies_thresholds() -> None:
    classifier = _FakeClassifier(
        {
            "strong": 0.5,
            "border": 0.15,
            "flat": 0.0,
            "soft-neg": -0.5,
        }
    )

    baseline = build_rule_sentiment_classifier(
        classifier, positive_threshold=0.2, negative_threshold=-0.2
    )
    sensitive = build_rule_sentiment_classifier(
        classifier, positive_threshold=0.1, negative_threshold=-0.1
    )

    assert baseline("strong") == "positive"
    assert baseline("border") == "neutral"
    assert baseline("flat") == "neutral"
    assert baseline("soft-neg") == "negative"

    # 更敏感的阈值把 border 判成 positive
    assert sensitive("border") == "positive"
    assert sensitive("flat") == "neutral"
