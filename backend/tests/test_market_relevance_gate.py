"""P1-4: 入库/候选阶段市场相关性门槛 + 官方源优先。"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.ingestion.persister import ItemPersister
from app.services.ingestion.types import SourceDefinition, SourceItem
from app.services.news_priority import (
    has_official_signal,
    passes_ingest_relevance_gate,
)


def test_has_official_signal_recognizes_ir_and_earnings_sources() -> None:
    assert has_official_signal("Company IR Portal") is True
    assert has_official_signal("Apple Investor Relations") is True
    assert has_official_signal("SEC EDGAR 8-K") is True
    assert has_official_signal("港交所公告") is True
    assert has_official_signal("Reuters", ("earnings", "guidance")) is True
    assert has_official_signal("TechCrunch Product Blog") is False


def test_passes_ingest_relevance_gate_rejects_weak_concept_mover_without_official() -> None:
    """提高门槛：仅「概念+涨停」弱信号、无官方源时不应入库。"""
    assert (
        passes_ingest_relevance_gate(
            title="某概念股涨停，市场热议",
            summary="题材炒作跟涨",
            source_name="WeChat Hot Takes",
        )
        is False
    )


def test_passes_ingest_relevance_gate_keeps_strong_market_signal() -> None:
    assert (
        passes_ingest_relevance_gate(
            title="NVIDIA raises revenue guidance amid AI demand",
            summary="Chipmaker lifts outlook for data-center GPUs",
            source_name="Reuters",
        )
        is True
    )


def test_passes_ingest_relevance_gate_prefers_official_source_even_if_weak_text() -> None:
    """官方/IR/监管源优先：弱文本也可过门槛。"""
    assert (
        passes_ingest_relevance_gate(
            title="Form 8-K filed",
            summary="Current report",
            source_name="SEC EDGAR",
        )
        is True
    )


def test_passes_ingest_relevance_gate_rejects_generic_tech_chatter() -> None:
    assert (
        passes_ingest_relevance_gate(
            title="Hands-on smartphone camera review for gaming laptops",
            summary="Benchmark battery and display impressions",
            source_name="Gadget Blog",
        )
        is False
    )


def test_persister_skips_low_relevance_new_items() -> None:
    session = MagicMock()
    session.scalar.return_value = None
    persister = ItemPersister(session, source_health_repository=MagicMock())
    persister.duplicate_gate = MagicMock()
    persister.duplicate_gate.find_duplicate.return_value = None

    source = SourceDefinition(
        name="Gadget Blog",
        source_type="rss",
        url="https://example.com/rss",
        market="us",
    )
    item = SourceItem(
        title="Hands-on smartphone camera review for gaming laptops",
        canonical_url="https://example.com/gadget-1",
        summary="Benchmark battery and display impressions",
        content_text=None,
        published_at=None,
    )

    assert persister.persist_item(source, item) is None
    session.add.assert_not_called()
