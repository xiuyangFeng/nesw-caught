"""Backward-compatible re-exports for news ingestion.

Public API:
    SourceDefinition, SourceItem, SourceFetchOutcome, SourceFetchResult,
    RefreshSummary, load_sources, NewsIngestionService
"""

from __future__ import annotations

from app.services.event_bus import get_event_bus
from app.services.http_client import HttpClientFactory
from app.services.ingestion.dedup_gate import (
    DuplicateGate,
    _build_duplicate_signature,
    _normalize_title_for_signature,
)
from app.services.ingestion.fetcher import fetch_source_items
from app.services.ingestion.parser import (
    _parse_anchor_list_html,
    _parse_minimax_detail_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_the_news_api_json,
    _parse_zhipu_news_inline_json,
)
from app.services.ingestion.persister import ItemPersister
from app.services.ingestion.service import NewsIngestionService
from app.services.ingestion.sources import load_sources
from app.services.ingestion.types import (
    DUPLICATE_WINDOW,
    LATENCY_EMA_ALPHA,
    MAX_FETCH_WORKERS,
    SOURCE_TIER_RANKS,
    VALID_SOURCE_TIERS,
    VALID_SOURCE_TYPES,
    RefreshSummary,
    SourceDefinition,
    SourceFetchOutcome,
    SourceFetchResult,
    SourceItem,
    SourceType,
)
from app.services.ingestion.utils import (
    _canonicalize_url,
    _clean_text,
    _ema_latency,
    _normalize_datetime,
    _parse_feed_datetime,
    _utc_now,
)
from app.services.news_signal_pipeline import NewsSignalPipelineService

__all__ = [
    "DUPLICATE_WINDOW",
    "HttpClientFactory",
    "LATENCY_EMA_ALPHA",
    "MAX_FETCH_WORKERS",
    "NewsIngestionService",
    "RefreshSummary",
    "SOURCE_TIER_RANKS",
    "SourceDefinition",
    "SourceFetchOutcome",
    "SourceFetchResult",
    "SourceItem",
    "SourceType",
    "VALID_SOURCE_TIERS",
    "VALID_SOURCE_TYPES",
    "get_event_bus",
    "load_sources",
    "NewsSignalPipelineService",
]
