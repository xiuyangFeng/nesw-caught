from __future__ import annotations

from app.schemas.research import (
    EvaluationMetrics,
    MarketRelevanceAnnotation,
    MarketRelevanceContent,
    MarketRelevanceLabel,
    MarketRelevanceOrigin,
    MarketRelevanceSample,
)
from app.services.news_relevance_evaluator import (
    EvaluationGuardrailError,
    evaluate_market_relevance,
    predict_market_relevance,
)


def _sample(sample_id: str, *, expected: bool, predicted: bool) -> MarketRelevanceSample:
    return MarketRelevanceSample(
        sample_id=sample_id,
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=1,
            source_name="Reuters",
            canonical_url=f"https://example.com/{sample_id}",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Market update",
            summary="Summary",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=expected,
            noise_type=None if expected else "off_topic",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    ).model_copy(update={"predicted_market_relevant": predicted})


def test_evaluator_reports_precision_recall_and_noise_rejection() -> None:
    samples = [
        _sample("tp", expected=True, predicted=True),
        _sample("fp", expected=False, predicted=True),
        _sample("tn", expected=False, predicted=False),
        _sample("fn", expected=True, predicted=False),
    ]

    result = evaluate_market_relevance(samples, min_recall=0.0)

    assert result.metrics == EvaluationMetrics(precision=0.5, recall=0.5, noise_rejection_rate=0.5)
    assert result.false_positive_ids == ["fp"]
    assert result.false_negative_ids == ["fn"]


def test_evaluator_rejects_results_below_recall_guardrail() -> None:
    samples = [
        _sample("fn-1", expected=True, predicted=False),
        _sample("fn-2", expected=True, predicted=False),
        _sample("tn", expected=False, predicted=False),
    ]

    try:
        evaluate_market_relevance(samples, min_recall=0.4)
    except EvaluationGuardrailError as exc:
        assert "recall" in str(exc)
        return

    raise AssertionError("expected recall guardrail to fail")


def test_predict_market_relevance_filters_generic_tech_chatter() -> None:
    sample = MarketRelevanceSample(
        sample_id="generic-tech",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=2,
            source_name="Tech Blog",
            canonical_url="https://example.com/generic-tech",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="New smartphone camera features impress reviewers",
            summary="A roundup of display, battery, and gaming upgrades.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=False,
            noise_type="generic_tech",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is False


def test_predict_market_relevance_keeps_market_moving_company_news() -> None:
    sample = MarketRelevanceSample(
        sample_id="company-event",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=3,
            source_name="Reuters",
            canonical_url="https://example.com/company-event",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Nvidia lifts revenue guidance after AI demand surge",
            summary="Analysts expect the stronger outlook to support semiconductor stocks.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is True


def test_evaluator_requires_explicit_predictions() -> None:
    sample = MarketRelevanceSample(
        sample_id="missing-prediction",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=4,
            source_name="Reuters",
            canonical_url="https://example.com/missing-prediction",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Oil prices move after OPEC talks",
            summary="Energy stocks were active in premarket trading.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=True,
            noise_type=None,
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    try:
        evaluate_market_relevance([sample], min_recall=0.0)
    except EvaluationGuardrailError as exc:
        assert "predicted_market_relevant" in str(exc)
        return

    raise AssertionError("expected evaluator to reject samples without explicit predictions")
