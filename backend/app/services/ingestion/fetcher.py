from __future__ import annotations

import time

from app.services.ingestion.parser import (
    _parse_anchor_list_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_the_news_api_json,
    _parse_zhipu_news_inline_json,
)
from app.services.ingestion.types import SourceDefinition, SourceFetchOutcome, SourceItem


def fetch_source_items(
    source: SourceDefinition,
    *,
    etag: str | None = None,
    last_modified: str | None = None
) -> SourceFetchOutcome:
    """纯网络抓取与解析,不触碰数据库,可在线程池中并发执行。"""
    from app.services import news_ingestion

    started = time.perf_counter()
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    try:
        with news_ingestion.HttpClientFactory().create() as client:
            try:
                response = client.get(source.url, headers=headers)
            except TypeError:
                response = client.get(source.url)

            status_code = getattr(response, "status_code", 200)
            if status_code == 304:
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                return SourceFetchOutcome(
                    source=source,
                    items=[],
                    error=None,
                    latency_ms=latency_ms,
                    etag=etag,
                    last_modified=last_modified,
                    is_not_modified=True,
                )

            response.raise_for_status()
            
            resp_headers = getattr(response, "headers", None) or {}
            new_etag = resp_headers.get("ETag")
            new_last_modified = resp_headers.get("Last-Modified")

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
        return SourceFetchOutcome(
            source=source,
            items=items,
            error=None,
            latency_ms=latency_ms,
            etag=new_etag,
            last_modified=new_last_modified,
        )
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return SourceFetchOutcome(
            source=source,
            items=[],
            error=str(exc),
            latency_ms=latency_ms,
            etag=etag,
            last_modified=last_modified,
        )
