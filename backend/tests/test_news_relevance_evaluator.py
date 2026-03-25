from __future__ import annotations

from dataclasses import dataclass

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
    predict_market_relevance_batch,
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


@dataclass
class _FakeClassificationResult:
    keywords: list[str]
    topic_key: str


class _FakeClassifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, str | None, bool]] = []

    def classify(
        self,
        *,
        title: str,
        summary: str | None,
        body: str | None,
        allow_llm: bool = True,
    ) -> _FakeClassificationResult:
        self.calls.append((title, summary, body, allow_llm))
        return _FakeClassificationResult(keywords=["revenue", "guidance"], topic_key="nvidia revenue")


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


def test_predict_market_relevance_keeps_chinese_earnings_flash() -> None:
    sample = MarketRelevanceSample(
        sample_id="earnings-flash-cn",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=7,
            source_name="CLS Telegraph",
            canonical_url="https://example.com/earnings-flash-cn",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="国药一致业绩快报：2025年净利润11.36亿元，同比增长76.8%",
            summary="公司披露最新业绩快报，净利润同比增长。",
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


def test_predict_market_relevance_keeps_buyback_and_dividend_updates() -> None:
    sample = MarketRelevanceSample(
        sample_id="buyback-dividend",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=8,
            source_name="CLS Telegraph",
            canonical_url="https://example.com/buyback-dividend",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="英伟达计划将50%的自由现金流用于回报投资者",
            summary="预计将在下半年回购股票，并派息。",
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


def test_predict_market_relevance_keeps_sec_fund_reporting_updates() -> None:
    sample = MarketRelevanceSample(
        sample_id="sec-fund-reporting",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=9,
            source_name="SEC",
            canonical_url="https://example.com/sec-fund-reporting",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="SEC Proposes Amendments to Reduce Burdens in Reporting of Fund Portfolio Holdings",
            summary="The proposal updates disclosure requirements for registered funds.",
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


def test_predict_market_relevance_does_not_treat_generic_sec_notice_as_market_signal() -> None:
    sample = MarketRelevanceSample(
        sample_id="sec-committee-notice",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=10,
            source_name="SEC",
            canonical_url="https://example.com/sec-committee-notice",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="SEC Seeks Candidates for Membership on the Investor Advisory Committee",
            summary="The Securities and Exchange Commission is seeking candidates for appointment as members of the SEC Investor Advisory Committee.",
            body_excerpt=None,
        ),
        labels=MarketRelevanceLabel(
            market_relevant=False,
            noise_type="low_information",
        ),
        annotation=MarketRelevanceAnnotation(
            label_source="human_reviewed",
            model_name="deepseek-chat",
            confidence=0.95,
            review_notes="",
        ),
    )

    assert predict_market_relevance(sample) is False


def test_predict_market_relevance_uses_classifier_with_body_excerpt() -> None:
    sample = MarketRelevanceSample(
        sample_id="body-assisted",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=5,
            source_name="Reuters",
            canonical_url="https://example.com/body-assisted",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Company update",
            summary="Short summary",
            body_excerpt="Detailed body text mentions revenue guidance for the next quarter.",
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
    classifier = _FakeClassifier()

    assert predict_market_relevance(sample, classifier=classifier) is True
    assert classifier.calls == [
        (
            "Company update",
            "Short summary",
            "Detailed body text mentions revenue guidance for the next quarter.",
            False,
        )
    ]


def test_predict_market_relevance_batch_stays_rule_only_when_ai_is_enabled(monkeypatch) -> None:
    sample = MarketRelevanceSample(
        sample_id="offline-batch",
        source_type="historical",
        origin=MarketRelevanceOrigin(
            news_id=6,
            source_name="Reuters",
            canonical_url="https://example.com/offline-batch",
            published_at="2026-03-25T00:00:00Z",
        ),
        content=MarketRelevanceContent(
            title="Nvidia lifts revenue guidance after AI demand surge",
            summary="Analysts expect the stronger outlook to support semiconductor stocks.",
            body_excerpt="Body text adds more demand and forecast detail.",
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

    monkeypatch.setattr(
        "app.services.news_signal_classifier.get_settings",
        lambda: type("Settings", (), {"ai_enabled": True})(),
    )
    monkeypatch.setattr(
        "app.services.news_signal_classifier.build_provider",
        lambda _config: (_ for _ in ()).throw(AssertionError("batch prediction must stay offline")),
    )

    predicted = predict_market_relevance_batch([sample], session=object())

    assert predicted[0].predicted_market_relevant is True


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
