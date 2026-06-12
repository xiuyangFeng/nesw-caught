from __future__ import annotations

import time

from app.services import news_ingestion
from app.services.ingestion.parser import (
    _parse_anchor_list_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_the_news_api_json,
    _parse_zhipu_news_inline_json,
)
from app.services.ingestion.types import SourceDefinition, SourceFetchOutcome, SourceItem


def fetch_source_items(source: SourceDefinition) -> SourceFetchOutcome:
    """纯网络抓取与解析,不触碰数据库,可在线程池中并发执行。"""
    started = time.perf_counter()
    try:
        with news_ingestion.HttpClientFactory().create() as client:
            response = client.get(source.url)
            response.raise_for_status()
            if source.source_type == "rss":
                items = _parse_rss_or_atom(response.text, source)
            elif source.source_type == "api":
                items = _parse_the_news_api_json(response.text, source)
            elif source.parser == "anchor_list_html":
                items = _parse_anchor_list_html(response.text, source)
            elif source.parser == "zhipu_news_inline_json":
                items = _parse_zhipu_news_inline_json(response.text, source)
            elif source.parser == "selector_html":
                items = _parse_selector_html(response.text, source)
            else:
                raise ValueError(f"unsupported parser for source {source.name}: {source.parser}")
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return SourceFetchOutcome(source=source, items=items, error=None, latency_ms=latency_ms)
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return SourceFetchOutcome(source=source, items=[], error=str(exc), latency_ms=latency_ms)
