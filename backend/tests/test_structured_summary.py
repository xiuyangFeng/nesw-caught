"""P1-4: 无 LLM 时结构化摘要（主体、事件、影响对象）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.db.session import SessionLocal
from app.services.news_signal_classifier import NewsSignalClassifier
from app.services.news_structured_summary import build_structured_takeaway
from app.services.news_takeaway import NewsTakeawayService


def test_build_structured_takeaway_includes_subject_event_impact() -> None:
    text = build_structured_takeaway(
        title="NVIDIA raises guidance on AI chip demand",
        keywords=["nvidia", "ai", "guidance"],
    )
    assert "：" in text
    assert "影响" in text
    assert "nvidia" in text.lower() or "英伟达" in text


def test_rule_classify_fills_takeaway_without_llm() -> None:
    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        with patch("app.services.news_signal_classifier.get_settings") as settings:
            settings.return_value.ai_enabled = False
            result = classifier.classify(
                title="Apple suppliers face tariff pressure on iPhone demand",
                summary="Supply chain outlook softens",
                body=None,
                allow_llm=False,
            )
    assert result.classifier_type == "rule"
    assert result.takeaway
    assert "：" in result.takeaway
    assert "影响" in result.takeaway


def test_takeaway_service_falls_back_to_structured_summary_without_llm_config() -> None:
    item = MagicMock()
    item.id = 1
    item.title = "Fed signals higher rates outlook"
    item.summary = "Policy remains restrictive"
    item.market = "us"
    item.ai_takeaway = None

    session = MagicMock()
    service = NewsTakeawayService(session)
    with (
        patch.object(service.config_repository, "get_active", return_value=None),
        patch.object(session, "scalars", return_value=iter([item])),
    ):
        updated = service.generate_for_ids([1], batch_limit=5)

    assert len(updated) == 1
    assert updated[0].ai_takeaway
    assert "：" in updated[0].ai_takeaway
    assert "影响" in updated[0].ai_takeaway
