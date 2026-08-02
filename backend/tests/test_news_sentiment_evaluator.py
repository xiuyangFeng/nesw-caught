from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.schemas.sentiment_eval import SentimentGoldSample
from app.services.news_sentiment_evaluator import (
    SentimentEvaluationError,
    build_hybrid_sentiment_classifier,
    build_rule_sentiment_classifier,
    compute_importance_weighted_accuracy,
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
    sentiment_label: str = "neutral"


class _FakeClassifier:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.calls: list[dict[str, object]] = []

    def classify(self, *, title: str, summary, body, allow_llm: bool = True):
        self.calls.append(
            {"title": title, "summary": summary, "body": body, "allow_llm": allow_llm}
        )
        return _FakeClassificationResult(sentiment_score=self.scores[title])


def _gold_sample(sample_id: str, text: str, **overrides) -> SentimentGoldSample:
    payload: dict[str, object] = {
        "sample_id": sample_id,
        "text": text,
        "sentiment_label": "neutral",
    }
    payload.update(overrides)
    return SentimentGoldSample(**payload)


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

    assert baseline(_gold_sample("s1", "strong")) == "positive"
    assert baseline(_gold_sample("s2", "border")) == "neutral"
    assert baseline(_gold_sample("s3", "flat")) == "neutral"
    assert baseline(_gold_sample("s4", "soft-neg")) == "negative"

    # 更敏感的阈值把 border 判成 positive
    assert sensitive(_gold_sample("s5", "border")) == "positive"
    assert sensitive(_gold_sample("s6", "flat")) == "neutral"

    # 离线评测必须 allow_llm=False。
    assert all(call["allow_llm"] is False for call in classifier.calls)


def test_build_rule_sentiment_classifier_aligns_input_with_online_path() -> None:
    """title=effective_title、summary/body 原样透传，与线上 classify 输入对齐。"""
    classifier = _FakeClassifier({"标题": 0.0})
    baseline = build_rule_sentiment_classifier(classifier)

    sample = _gold_sample(
        "s1", "fallback-text", title="标题", summary="摘要内容", body="正文内容"
    )
    baseline(sample)

    assert classifier.calls[-1] == {
        "title": "标题",
        "summary": "摘要内容",
        "body": "正文内容",
        "allow_llm": False,
    }


def test_build_rule_sentiment_classifier_falls_back_to_text_when_title_missing() -> None:
    classifier = _FakeClassifier({"legacy-text": 0.0})
    baseline = build_rule_sentiment_classifier(classifier)

    sample = _gold_sample("s1", "legacy-text")
    baseline(sample)

    assert classifier.calls[-1]["title"] == "legacy-text"
    assert classifier.calls[-1]["summary"] is None
    assert classifier.calls[-1]["body"] is None


def test_build_hybrid_sentiment_classifier_uses_allow_llm_true_and_label() -> None:
    class _HybridFake:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def classify(self, *, title, summary, body, allow_llm):
            self.calls.append(
                {"title": title, "summary": summary, "body": body, "allow_llm": allow_llm}
            )
            return _FakeClassificationResult(sentiment_score=0.9, sentiment_label="positive")

    fake = _HybridFake()
    hybrid = build_hybrid_sentiment_classifier(fake)
    sample = _gold_sample("s1", "text", title="标题", summary="摘要", body="正文")

    assert hybrid(sample) == "positive"
    assert fake.calls == [
        {"title": "标题", "summary": "摘要", "body": "正文", "allow_llm": True}
    ]


def test_compute_importance_weighted_accuracy_none_when_no_importance() -> None:
    samples = [
        _gold_sample("s1", "a", sentiment_label="positive"),
        _gold_sample("s2", "b", sentiment_label="negative"),
    ]
    assert compute_importance_weighted_accuracy(samples, ["positive", "negative"]) is None


def test_compute_importance_weighted_accuracy_none_on_empty_samples() -> None:
    assert compute_importance_weighted_accuracy([], []) is None


def test_compute_importance_weighted_accuracy_weights_annotated_samples() -> None:
    samples = [
        _gold_sample("s1", "a", sentiment_label="positive", importance=1.0),
        # 无 importance 标注 => 权重按 1.0 计。
        _gold_sample("s2", "b", sentiment_label="negative"),
        _gold_sample("s3", "c", sentiment_label="neutral", importance=0.5),
    ]
    # s1 命中(权重1)，s2 命中(权重1)，s3 未命中(权重0.5)
    # accuracy = (1+1)/(1+1+0.5) = 0.8
    result = compute_importance_weighted_accuracy(samples, ["positive", "negative", "positive"])
    assert result == 0.8
