from __future__ import annotations

import pytest

from app.schemas.sentiment_eval import SentimentGoldSample
from app.services.news_sentiment_dataset import load_gold_samples
from app.services.news_sentiment_evaluator import SentimentEvaluationError
from app.services.news_sentiment_experiment_runner import (
    compare_sentiment_runs,
    run_sentiment_ab,
    run_sentiment_evaluation,
)


def _samples() -> list[SentimentGoldSample]:
    return [
        SentimentGoldSample(sample_id="a", text="a", sentiment_label="positive"),
        SentimentGoldSample(sample_id="b", text="b", sentiment_label="positive"),
        SentimentGoldSample(sample_id="c", text="c", sentiment_label="negative"),
        SentimentGoldSample(sample_id="d", text="d", sentiment_label="neutral"),
    ]


def _classify_from(mapping: dict[str, str]):
    def classify(text: str) -> str:
        return mapping[text]

    return classify


def test_run_sentiment_evaluation_uses_injected_classifier() -> None:
    classify = _classify_from({"a": "positive", "b": "negative", "c": "negative", "d": "neutral"})

    run = run_sentiment_evaluation(_samples(), model_name="mock", classify_fn=classify)

    assert run.model_name == "mock"
    assert run.metrics.accuracy == 0.75
    assert run.metrics.macro_f1 == 0.7778
    labels = {row.label: row for row in run.metrics.per_label}
    assert labels["positive"].recall == 0.5
    assert labels["negative"].precision == 0.5


def test_run_sentiment_ab_picks_better_model() -> None:
    model_a = _classify_from({"a": "positive", "b": "negative", "c": "negative", "d": "neutral"})
    model_b = _classify_from({"a": "positive", "b": "positive", "c": "negative", "d": "neutral"})

    comparison = run_sentiment_ab(
        _samples(),
        model_a_name="baseline",
        model_a_classify=model_a,
        model_b_name="candidate",
        model_b_classify=model_b,
    )

    assert comparison.model_a.metrics.accuracy == 0.75
    assert comparison.model_b.metrics.accuracy == 1.0
    assert comparison.accuracy_delta == 0.25
    assert comparison.macro_f1_delta == 0.2222
    assert comparison.winner == "model_b"

    deltas = {row.label: row for row in comparison.label_deltas}
    assert deltas["positive"].f1_before == 0.6667
    assert deltas["positive"].f1_after == 1.0
    assert deltas["positive"].f1_delta == 0.3333
    assert deltas["neutral"].f1_delta == 0.0


def test_run_sentiment_ab_reports_tie_for_identical_models() -> None:
    mapping = {"a": "positive", "b": "positive", "c": "negative", "d": "neutral"}
    comparison = run_sentiment_ab(
        _samples(),
        model_a_name="baseline",
        model_a_classify=_classify_from(mapping),
        model_b_name="candidate",
        model_b_classify=_classify_from(dict(mapping)),
    )

    assert comparison.winner == "tie"
    assert comparison.macro_f1_delta == 0.0
    assert comparison.accuracy_delta == 0.0


def test_compare_sentiment_runs_detects_regression() -> None:
    better = _classify_from({"a": "positive", "b": "positive", "c": "negative", "d": "neutral"})
    worse = _classify_from({"a": "positive", "b": "negative", "c": "negative", "d": "neutral"})

    run_a = run_sentiment_evaluation(_samples(), model_name="baseline", classify_fn=better)
    run_b = run_sentiment_evaluation(_samples(), model_name="candidate", classify_fn=worse)

    comparison = compare_sentiment_runs(run_a, run_b)

    assert comparison.winner == "model_a"
    assert comparison.macro_f1_delta < 0


def test_missing_dataset_degrades_gracefully(tmp_path) -> None:
    # 金标文件不存在 -> 空列表（不抛异常），再评测则给出明确的空数据错误
    missing = tmp_path / "does_not_exist.json"
    samples = load_gold_samples(missing)
    assert samples == []

    with pytest.raises(SentimentEvaluationError):
        run_sentiment_evaluation(
            samples, model_name="mock", classify_fn=lambda _text: "neutral"
        )
