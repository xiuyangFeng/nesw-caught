"""sentiment_eval_persistence 纯函数测试：序列化往返、comparison 选择、历史摘要、回归判定。"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.sentiment_eval_run import SentimentEvalRun
from app.schemas.sentiment_eval import (
    SentimentEvaluationMetrics,
    SentimentLabelMetrics,
    SentimentModelRun,
)
from app.services.sentiment_eval_persistence import (
    build_history,
    compute_dataset_hash,
    compute_regression,
    deserialize_run,
    pick_comparison,
    serialize_run_for_storage,
)

_LABEL_ROW = SentimentLabelMetrics(label="positive", precision=1.0, recall=1.0, f1=1.0, support=1)


def _metrics(accuracy: float, macro_f1: float, importance: float | None = None) -> SentimentEvaluationMetrics:
    return SentimentEvaluationMetrics(
        accuracy=accuracy,
        macro_f1=macro_f1,
        sample_count=3,
        per_label=[_LABEL_ROW],
        confusion_matrix={"positive": {"positive": 1, "negative": 0, "neutral": 0}},
        importance_weighted_accuracy=importance,
    )


def _run(model_name: str, accuracy: float, macro_f1: float, importance: float | None = None) -> SentimentModelRun:
    return SentimentModelRun(model_name=model_name, metrics=_metrics(accuracy, macro_f1, importance))


def _row(model_name: str, accuracy: float, macro_f1: float, **overrides) -> SentimentEvalRun:
    payload = dict(
        batch_id="batch-1",
        created_at=datetime.now(UTC),
        dataset_path="data/x.json",
        dataset_hash="hash-a",
        sample_count=3,
        model_name=model_name,
        config_json=None,
        accuracy=accuracy,
        macro_f1=macro_f1,
        importance_weighted_accuracy=None,
        per_label_json='[{"label": "positive", "precision": 1.0, "recall": 1.0, "f1": 1.0, "support": 1}]',
        confusion_json='{"positive": {"positive": 1, "negative": 0, "neutral": 0}}',
        note=None,
    )
    payload.update(overrides)
    return SentimentEvalRun(**payload)


def test_compute_dataset_hash_matches_sha256_first_16_chars(tmp_path) -> None:
    import hashlib

    path = tmp_path / "gold.json"
    path.write_text("[]", encoding="utf-8")

    expected = hashlib.sha256(b"[]").hexdigest()[:16]
    assert compute_dataset_hash(path) == expected
    assert len(compute_dataset_hash(path)) == 16


def test_compute_dataset_hash_changes_with_content(tmp_path) -> None:
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    path_a.write_text('[{"a": 1}]', encoding="utf-8")
    path_b.write_text('[{"a": 2}]', encoding="utf-8")

    assert compute_dataset_hash(path_a) != compute_dataset_hash(path_b)


def test_serialize_and_deserialize_round_trip() -> None:
    run = _run("llm:openai/gpt", 0.8, 0.75, importance=0.79)

    storage = serialize_run_for_storage(run)
    row = _row(
        run.model_name,
        run.metrics.accuracy,
        run.metrics.macro_f1,
        per_label_json=storage["per_label_json"],
        confusion_json=storage["confusion_json"],
        importance_weighted_accuracy=storage["importance_weighted_accuracy"],
    )

    restored = deserialize_run(row)

    assert restored.model_name == run.model_name
    assert restored.metrics.accuracy == run.metrics.accuracy
    assert restored.metrics.macro_f1 == run.metrics.macro_f1
    assert restored.metrics.importance_weighted_accuracy == 0.79
    assert restored.metrics.per_label == run.metrics.per_label
    assert restored.metrics.confusion_matrix == run.metrics.confusion_matrix


def test_pick_comparison_prefers_llm_model_b() -> None:
    runs = [
        _run("rule-baseline", 0.7, 0.68),
        _run("llm:openai/gpt", 0.85, 0.82),
        _run("hybrid:openai/gpt", 0.83, 0.80),
    ]

    comparison = pick_comparison(runs)

    assert comparison is not None
    assert comparison.model_a.model_name == "rule-baseline"
    assert comparison.model_b.model_name == "llm:openai/gpt"


def test_pick_comparison_falls_back_to_rule_sensitive_without_llm() -> None:
    runs = [
        _run("rule-baseline", 0.7, 0.68),
        _run("rule-sensitive (±0.10)", 0.72, 0.70),
    ]

    comparison = pick_comparison(runs)

    assert comparison is not None
    assert comparison.model_b.model_name == "rule-sensitive (±0.10)"


def test_pick_comparison_returns_none_without_rule_baseline() -> None:
    runs = [_run("llm:openai/gpt", 0.85, 0.82)]
    assert pick_comparison(runs) is None


def test_pick_comparison_returns_none_without_any_model_b_candidate() -> None:
    runs = [_run("rule-baseline", 0.7, 0.68)]
    assert pick_comparison(runs) is None


def test_build_history_summarizes_batches() -> None:
    batch_new = [_row("rule-baseline", 0.7, 0.68), _row("llm:openai/gpt", 0.85, 0.82)]
    batch_old = [_row("rule-baseline", 0.66, 0.64)]

    history = build_history([batch_new, batch_old])

    assert len(history) == 2
    assert history[0].batch_id == "batch-1"
    assert history[0].sample_count == 3
    assert [entry.model_name for entry in history[0].entries] == ["rule-baseline", "llm:openai/gpt"]
    assert history[0].entries[1].macro_f1 == 0.82


def test_build_history_skips_empty_batches() -> None:
    assert build_history([[], []]) == []


def test_compute_regression_returns_none_without_previous_batch() -> None:
    worst, others = compute_regression(previous_batch=[], current_runs=[_run("rule-baseline", 0.7, 0.68)])
    assert worst is None
    assert others == []


def test_compute_regression_detects_drop_over_threshold() -> None:
    previous = [_row("llm:openai/gpt", 0.88, 0.86)]
    current = [_run("llm:openai/gpt", 0.83, 0.82)]

    worst, others = compute_regression(previous_batch=previous, current_runs=current)

    assert worst is not None
    assert worst.model_name == "llm:openai/gpt"
    assert worst.previous_macro_f1 == 0.86
    assert worst.current_macro_f1 == 0.82
    assert worst.delta == -0.04
    assert worst.regressed is True
    assert others == []


def test_compute_regression_not_regressed_when_drop_within_threshold() -> None:
    previous = [_row("rule-baseline", 0.70, 0.68)]
    current = [_run("rule-baseline", 0.70, 0.67)]  # -0.01，未超过 0.02 阈值

    worst, others = compute_regression(previous_batch=previous, current_runs=current)

    assert worst is not None
    assert worst.regressed is False
    assert worst.delta == -0.01


def test_compute_regression_picks_worst_and_reports_others() -> None:
    previous = [
        _row("rule-baseline", 0.70, 0.68),
        _row("llm:openai/gpt", 0.88, 0.86),
        _row("hybrid:openai/gpt", 0.84, 0.81),
    ]
    current = [
        _run("rule-baseline", 0.70, 0.68),  # 无变化
        _run("llm:openai/gpt", 0.83, 0.80),  # -0.06，回归且最差
        _run("hybrid:openai/gpt", 0.79, 0.76),  # -0.05，回归但不是最差
    ]

    worst, others = compute_regression(previous_batch=previous, current_runs=current)

    assert worst is not None
    assert worst.model_name == "llm:openai/gpt"
    assert [item.model_name for item in others] == ["hybrid:openai/gpt"]


def test_compute_regression_ignores_models_without_previous_counterpart() -> None:
    previous = [_row("rule-baseline", 0.70, 0.68)]
    current = [_run("rule-baseline", 0.70, 0.68), _run("llm:openai/gpt", 0.85, 0.82)]

    worst, others = compute_regression(previous_batch=previous, current_runs=current)

    assert worst is not None
    assert worst.model_name == "rule-baseline"
    assert others == []
