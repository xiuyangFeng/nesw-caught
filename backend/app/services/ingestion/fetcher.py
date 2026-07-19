from __future__ import annotations

import logging
import time

from app.services import http_pool
from app.services.ingestion.parser import (
    _parse_anchor_list_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_the_news_api_json,
    _parse_zhipu_news_inline_json,
)
from app.services.ingestion.types import SourceDefinition, SourceFetchOutcome

logger = logging.getLogger(__name__)


def fetch_source_items(
    source: SourceDefinition,
    *,
    etag: str | None = None,
    last_modified: str | None = None
) -> SourceFetchOutcome:
    """纯网络抓取与解析,不触碰数据库,可在线程池中并发执行。"""
    started = time.perf_counter()
    logger.info(
        "news source fetch started: source=%s type=%s url=%s",
        source.name,
        source.source_type,
        source.url,
    )
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    try:
        # 共享 feed client(httpx.Client 线程安全):跨源跨轮复用 TCP/TLS 连接,
        # 不要在这里 close,进程退出时由 http_pool.close_llm_client() 统一回收。
        client = http_pool.get_feed_client()
        try:
            response = client.get(source.url, headers=headers)
        except TypeError:
            response = client.get(source.url)

        status_code = getattr(response, "status_code", 200)
        if status_code == 304:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "news source fetch not modified: source=%s type=%s latency_ms=%s",
                source.name,
                source.source_type,
                latency_ms,
            )
            return SourceFetchOutcome(
                source=source,
                items=[],
                error=None,
                latency_ms=latency_ms,
                etag=etag,
                last_modified=last_modified,
                is_not_modified=True,
                http_status=304,
            )

        try:
            response.raise_for_status()
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return SourceFetchOutcome(
                source=source,
                items=[],
                error=str(exc),
                latency_ms=latency_ms,
                etag=etag,
                last_modified=last_modified,
                http_status=status_code,
                error_kind="http_error",
            )

        resp_headers = getattr(response, "headers", None) or {}
        new_etag = resp_headers.get("ETag")
        new_last_modified = resp_headers.get("Last-Modified")

        try:
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
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.warning(
                "news source parse failed: source=%s type=%s url=%s latency_ms=%s error=%s",
                source.name,
                source.source_type,
                source.url,
                latency_ms,
                exc,
                exc_info=True,
            )
            return SourceFetchOutcome(
                source=source,
                items=[],
                error=str(exc),
                latency_ms=latency_ms,
                etag=new_etag,
                last_modified=new_last_modified,
                http_status=status_code,
                error_kind="parse_error",
            )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "news source fetch succeeded: source=%s type=%s items=%s latency_ms=%s",
            source.name,
            source.source_type,
            len(items),
            latency_ms,
        )
        return SourceFetchOutcome(
            source=source,
            items=items,
            error=None,
            latency_ms=latency_ms,
            etag=new_etag,
            last_modified=new_last_modified,
            http_status=status_code,
        )
    except Exception as exc:
        # 兜底范围刻意保持宽泛:本函数运行在 ThreadPoolExecutor 的工作线程中,
        # 调用方 (service.refresh_all) 用 `[f.result() for f in futures]` 收集结果,
        # 未对单个 future 做 try/except —— 这里一旦让异常逃逸,会在 f.result() 处
        # 直接抛出并中断整批 source 的抓取。可能出现的异常横跨 httpx 网络层
        # (含不属于 httpx.HTTPError 体系的 httpx.InvalidURL/StreamError)、
        # xml.etree.ElementTree.ParseError、json.JSONDecodeError、显式 ValueError
        # 与 BeautifulSoup 解析期间的杂项异常,无法安全穷举收窄,因此维持 Exception 兜底,
        # 仅补充带 source 上下文的日志。
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.warning(
            "news source fetch failed: source=%s type=%s url=%s latency_ms=%s error=%s",
            source.name,
            source.source_type,
            source.url,
            latency_ms,
            exc,
            exc_info=True,
        )
        return SourceFetchOutcome(
            source=source,
            items=[],
            error=str(exc),
            latency_ms=latency_ms,
            etag=etag,
            last_modified=last_modified,
            error_kind="http_error",
        )
