from unittest.mock import patch

from app.db.session import SessionLocal
from app.services import news_signal_classifier as classifier_module
from app.services.news_signal_classifier import ClassificationResult, NewsSignalClassifier


class _FakeProvider:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def analyze_json(
        self,
        *,
        prompt: str,
        title=None,
        summary=None,
        market=None,
        system_prompt=None,
        cache_scope=None,
    ) -> object:
        assert "takeaway" in prompt
        return self._payload


def _baseline() -> ClassificationResult:
    return ClassificationResult(
        sentiment_label="neutral",
        sentiment_score=0.0,
        signal_confidence=0.4,
        keywords=["ai"],
        topic_key="ai",
        summary="s",
        classifier_type="rule",
    )


def _refine(payload: object) -> ClassificationResult:
    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        with (
            patch.object(classifier.config_repository, "get_active", return_value=object()),
            patch.object(classifier_module, "build_provider", return_value=_FakeProvider(payload)),
        ):
            return classifier._llm_refine(_baseline(), title="t", summary="s", body="b")


def test_classification_result_defaults_takeaway_none() -> None:
    assert _baseline().takeaway is None


def test_llm_refine_parses_and_trims_takeaway() -> None:
    result = _refine({"takeaway": "  英伟达产业链受益,偏利好。 "})
    assert result.takeaway == "英伟达产业链受益,偏利好。"


def test_llm_refine_truncates_long_takeaway() -> None:
    result = _refine({"takeaway": "长" * 300})
    assert result.takeaway is not None
    assert len(result.takeaway) == 120


def test_llm_refine_tolerates_missing_takeaway_key() -> None:
    result = _refine({"sentiment_label": "positive"})
    assert result.takeaway is None
