from __future__ import annotations

from pydantic import ValidationError

from app.schemas.research import ExperimentDecision, MarketRelevanceSample


def test_market_relevance_sample_requires_noise_type_for_negative_label() -> None:
    try:
        MarketRelevanceSample.model_validate(
            {
                "sample_id": "hist-0001",
                "source_type": "historical",
                "origin": {
                    "news_id": 1,
                    "source_name": "Reuters",
                    "canonical_url": "https://example.com/news/1",
                    "published_at": "2026-03-25T00:00:00Z",
                },
                "content": {
                    "title": "General gadget launch roundup",
                    "summary": "Consumer gadget coverage only.",
                    "body_excerpt": None,
                },
                "labels": {
                    "market_relevant": False,
                    "noise_type": None,
                },
                "annotation": {
                    "label_source": "human_reviewed",
                    "model_name": "deepseek-chat",
                    "confidence": 0.91,
                    "review_notes": "",
                },
            }
        )
    except ValidationError:
        return

    raise AssertionError("expected ValidationError when negative label omits noise_type")


def test_experiment_decision_rejects_metric_regression_without_reason() -> None:
    try:
        ExperimentDecision.model_validate(
            {
                "experiment_id": "exp-001",
                "decision": "reject",
                "reason": "",
                "metrics_before": {"precision": 0.62, "recall": 0.55, "noise_rejection_rate": 0.7},
                "metrics_after": {"precision": 0.6, "recall": 0.54, "noise_rejection_rate": 0.69},
            }
        )
    except ValidationError:
        return

    raise AssertionError("expected ValidationError when reject decision omits reason")


def test_experiment_decision_allows_baseline_rows() -> None:
    decision = ExperimentDecision.model_validate(
        {
            "experiment_id": "baseline-001",
            "decision": "baseline",
            "reason": "initial baseline capture",
            "metrics_before": {"precision": 0.62, "recall": 0.55, "noise_rejection_rate": 0.7},
            "metrics_after": {"precision": 0.62, "recall": 0.55, "noise_rejection_rate": 0.7},
        }
    )

    assert decision.decision == "baseline"
