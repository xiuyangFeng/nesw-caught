from __future__ import annotations

import hashlib
import logging
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.services import http_pool
from app.services.ingestion.parser import (
    _parse_anchor_list_html,
    _parse_cls_telegraph_json,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_the_news_api_json,
    _parse_wallstreetcn_live_json,
    _parse_zhipu_news_inline_json,
)
from app.services.ingestion.types import SourceDefinition, SourceFetchOutcome

logger = logging.getLogger(__name__)


DEFAULT_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ---------------------------------------------------------------------------
# 财联社 7x24 快讯官方 JSON 接口
#
# cls.cn/telegraph 现在是 Next.js SSR 空壳（页面里没有任何新闻数据），必须改走
# /v1/roll/get_roll_list。该接口要求：
#   1) Referer 必须是 https://www.cls.cn/telegraph，否则被拒；
#   2) 查询参数按 key 升序拼成 k1=v1&k2=v2，先 sha1 取 hexdigest，
#      再对该 hexdigest 做 md5 取 hexdigest，作为 sign 附加。
# 签名与 Referer 在 fetcher 层构造，sources.py 只填基础 endpoint。
# ---------------------------------------------------------------------------
CLS_PARSER = "cls_telegraph_json"
CLS_REFERER = "https://www.cls.cn/telegraph"
CLS_BASE_PARAMS: dict[str, str] = {
    "app": "CailianpressWeb",
    "os": "web",
    "sv": "8.4.6",
    "last_time": "",
    "category": "",
}


def cls_sign(params: dict[str, str]) -> str:
    """财联社签名：sorted(k=v) 拼接 → sha1 hexdigest → md5 hexdigest。"""
    payload = "&".join(f"{key}={params[key]}" for key in sorted(params))
    return hashlib.md5(hashlib.sha1(payload.encode()).hexdigest().encode()).hexdigest()


def build_cls_request(source: SourceDefinition) -> tuple[str, dict[str, str]]:
    """为财联社 JSON 源构造带签名的 URL 与附加请求头。

    endpoint 上已有的查询参数会被保留并一起参与签名（覆盖默认值），
    这样 sources.py 之后调整 category 之类的参数无需改动本函数。
    """
    parts = urlsplit(source.url)
    params = dict(CLS_BASE_PARAMS)
    params.update(dict(parse_qsl(parts.query, keep_blank_values=True)))
    params.pop("sign", None)
    params["rn"] = str(max(1, min(int(source.item_limit or 20), 50)))

    params["sign"] = cls_sign(params)
    signed_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))
    return signed_url, {"Referer": CLS_REFERER, "Accept": "application/json, text/plain, */*"}


def _describe_exception(exc: BaseException) -> str:
    """异常描述统一带上类型名。

    httpx 的超时/连接类异常 `str(exc)` 常常是空串 —— 线上 source_health.last_error
    因此全部为空字符串，故障完全不可诊断。
    """
    detail = str(exc).strip()
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def _classify_network_error(exc: BaseException) -> str:
    """把网络异常细分为 timeout / connect_error / http_error，便于上层退避策略区分。"""
    names = {klass.__name__ for klass in type(exc).__mro__}
    if names & {"TimeoutException", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout", "Timeout"}:
        return "timeout"
    if names & {"ConnectError", "ConnectionError", "NetworkError", "ProxyError", "gaierror"}:
        return "connect_error"
    return "http_error"


def _get_with_headers(client, url: str, headers: dict[str, str]):
    """带条件头发起 GET；仅当客户端确实不接受 headers 参数时才降级重试。

    历史实现对任何 TypeError 都无脑降级重发一次不带条件头的请求，
    真实 httpx 内部抛出的 TypeError 会被吞掉并造成「双倍请求 + 丢失 ETag 语义」。
    这里只在异常信息明确指向 headers 关键字参数时才回退（测试里的 FakeClient 场景）。
    """
    try:
        return client.get(url, headers=headers)
    except TypeError as exc:
        message = str(exc)
        if "headers" not in message:
            raise
        logger.warning(
            "feed client rejected headers kwarg, retrying without conditional headers: url=%s error=%s",
            url,
            _describe_exception(exc),
        )
        return client.get(url)


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
    headers = dict(DEFAULT_FETCH_HEADERS)
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    request_url = source.url
    if source.parser == CLS_PARSER:
        request_url, extra_headers = build_cls_request(source)
        headers.update(extra_headers)

    try:
        # 共享 feed client(httpx.Client 线程安全):跨源跨轮复用 TCP/TLS 连接,
        # 不要在这里 close,进程退出时由 http_pool.close_llm_client() 统一回收。
        client = http_pool.get_feed_client()
        response = _get_with_headers(client, request_url, headers)

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
            logger.warning(
                "news source http status error: source=%s type=%s url=%s status=%s error=%s",
                source.name,
                source.source_type,
                source.url,
                status_code,
                _describe_exception(exc),
            )
            return SourceFetchOutcome(
                source=source,
                items=[],
                error=_describe_exception(exc),
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
            elif source.parser == "wallstreetcn_live_json":
                items = _parse_wallstreetcn_live_json(response.text, source)
            elif source.parser == CLS_PARSER:
                items = _parse_cls_telegraph_json(response.text, source)
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
                _describe_exception(exc),
                exc_info=True,
            )
            return SourceFetchOutcome(
                source=source,
                items=[],
                error=_describe_exception(exc),
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
        error_kind = _classify_network_error(exc)
        logger.warning(
            "news source fetch failed: source=%s type=%s url=%s latency_ms=%s error_kind=%s error=%s",
            source.name,
            source.source_type,
            source.url,
            latency_ms,
            error_kind,
            _describe_exception(exc),
            exc_info=True,
        )
        return SourceFetchOutcome(
            source=source,
            items=[],
            error=_describe_exception(exc),
            latency_ms=latency_ms,
            etag=etag,
            last_modified=last_modified,
            error_kind=error_kind,
        )
