from __future__ import annotations

from dataclasses import dataclass
import re

from app.schemas.research import EvaluationMetrics, MarketRelevanceSample
from app.services.news_signal_classifier import NewsSignalClassifier

MARKET_SIGNAL_TERMS = {
    "guidance",
    "revenue",
    "earnings",
    "fund",
    "funds",
    "portfolio",
    "holdings",
    "tariff",
    "policy",
    "regulation",
    "acquisition",
    "merger",
    "demand",
    "supply",
    "shipment",
    "outlook",
    "shares",
    "stock",
    "stocks",
    "profit",
    "forecast",
    "rates",
    "bank",
    "fed",
    "ipo",
}

MARKET_SIGNAL_PHRASES = {
    "sec proposes",
    "sec announces enforcement",
    "fund portfolio holdings",
    "reporting of fund",
    "buyback",
    "dividend",
    "share repurchase",
}

CHINESE_MARKET_SIGNAL_PHRASES = {
    "业绩快报",
    "净利润",
    "回购股票",
    "派息",
    "股东",
    "减持",
    "增持",
    "沪指",
    "深成指",
    "股指",
    "指数",
    "收盘上涨",
    "电池级碳酸锂",
    "市场稳定计划",
    "期货",
    "自由现金流",
}

CHINESE_CONCEPT_SIGNAL_TERMS = {
    "概念",
    "板块",
}

CHINESE_EQUITY_MOVE_TERMS = {
    "涨停",
    "跟涨",
}

GENERIC_TECH_TERMS = {
    "camera",
    "reviewers",
    "display",
    "battery",
    "gaming",
    "smartphone",
    "laptop",
    "hands-on",
    "benchmark",
}

SHIPPING_ROUTE_TERMS = {"shipper", "shippers", "shipping", "container", "operators"}
SHIPPING_DISRUPTION_PHRASES = {"red sea", "route", "routes", "targeting"}


class EvaluationGuardrailError(ValueError):
    pass


@dataclass(frozen=True)
class MarketRelevanceEvaluationResult:
    metrics: EvaluationMetrics
    false_positive_ids: list[str]
    false_negative_ids: list[str]


def evaluate_market_relevance(
    samples: list[MarketRelevanceSample],
    *,
    min_recall: float = 0.0,
) -> MarketRelevanceEvaluationResult:
    tp = fp = tn = fn = 0
    false_positive_ids: list[str] = []
    false_negative_ids: list[str] = []

    for sample in samples:
        if sample.predicted_market_relevant is None:
            raise EvaluationGuardrailError(
                f"sample {sample.sample_id} is missing predicted_market_relevant"
            )
        predicted = sample.predicted_market_relevant
        expected = sample.labels.market_relevant
        if predicted and expected:
            tp += 1
        elif predicted and not expected:
            fp += 1
            false_positive_ids.append(sample.sample_id)
        elif not predicted and expected:
            fn += 1
            false_negative_ids.append(sample.sample_id)
        else:
            tn += 1

    precision = _safe_divide(tp, tp + fp)
    recall = _safe_divide(tp, tp + fn)
    noise_rejection_rate = _safe_divide(tn, tn + fp)
    if recall < min_recall:
        raise EvaluationGuardrailError(f"recall {recall:.4f} fell below guardrail {min_recall:.4f}")

    return MarketRelevanceEvaluationResult(
        metrics=EvaluationMetrics(
            precision=round(precision, 4),
            recall=round(recall, 4),
            noise_rejection_rate=round(noise_rejection_rate, 4),
        ),
        false_positive_ids=false_positive_ids,
        false_negative_ids=false_negative_ids,
    )


def predict_market_relevance(
    sample: MarketRelevanceSample,
    *,
    classifier: NewsSignalClassifier | object | None = None,
) -> bool:
    raw_text = " ".join(
        part
        for part in [
            sample.content.title,
            sample.content.summary or "",
            sample.content.body_excerpt or "",
        ]
        if part
    )
    text = raw_text.lower()
    tokens = set(re.findall(r"[a-z0-9]+", text))
    classifier_tokens: set[str] = set()
    if classifier is not None:
        result = classifier.classify(
            title=sample.content.title,
            summary=sample.content.summary,
            body=sample.content.body_excerpt,
            allow_llm=False,
        )
        classifier_tokens = set(getattr(result, "keywords", []))
        classifier_tokens.update(re.findall(r"[a-z0-9]+", getattr(result, "topic_key", "")))

    combined_market_tokens = tokens.union(classifier_tokens)
    if combined_market_tokens.intersection(MARKET_SIGNAL_TERMS):
        return True
    if any(phrase in text for phrase in MARKET_SIGNAL_PHRASES):
        return True
    if any(phrase in raw_text for phrase in CHINESE_MARKET_SIGNAL_PHRASES):
        return True
    if _looks_like_chinese_concept_mover(raw_text):
        return True
    if combined_market_tokens.intersection(SHIPPING_ROUTE_TERMS) and any(
        phrase in text for phrase in SHIPPING_DISRUPTION_PHRASES
    ):
        return True
    if tokens.intersection(GENERIC_TECH_TERMS) or classifier_tokens.intersection(GENERIC_TECH_TERMS):
        return False
    return False


def predict_market_relevance_batch(
    samples: list[MarketRelevanceSample],
    *,
    session,
) -> list[MarketRelevanceSample]:
    classifier = NewsSignalClassifier(session)
    return [
        sample.model_copy(update={"predicted_market_relevant": predict_market_relevance(sample, classifier=classifier)})
        for sample in samples
    ]


def _safe_divide(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _looks_like_chinese_concept_mover(raw_text: str) -> bool:
    return any(term in raw_text for term in CHINESE_CONCEPT_SIGNAL_TERMS) and any(
        term in raw_text for term in CHINESE_EQUITY_MOVE_TERMS
    )
