"""进程内共享的 httpx 连接池。

2026-07-25 重构要点:
1. 所有 client 的超时从标量改为 ``httpx.Timeout``。标量 timeout 会被 httpx
   同时用于 connect/read/write/pool 四个阶段,于是"建连慢 + 读取慢"会叠加,
   单次 LLM 请求的最坏耗时可以是 ``llm_timeout_seconds`` 的数倍;叠加重试与
   failover 后单条新闻的最坏等待可达数分钟。这里把建连单独收紧到
   ``http_connect_timeout_seconds``。
2. 增加"已终止"终态标志。此前 ``close_llm_client()`` 只是把全局变量置 None,
   任何仍在运行的 daemon 线程再调一次 getter 就会静默重建连接池,导致关停后
   连接仍在泄漏。``shutdown_http_pools()`` 进入终态后 getter 直接抛错。
   注意 ``close_llm_client()`` 保持原有的"关闭 + 允许惰性重建"语义(测试与
   conftest 依赖它),终态只由显式的 shutdown 入口进入。
"""

from __future__ import annotations

import threading

import httpx

from app.core.config import get_settings

_client: httpx.Client | None = None
_async_client: httpx.AsyncClient | None = None
_crawl_client: httpx.Client | None = None
_feed_client: httpx.Client | None = None
_feishu_client: httpx.Client | None = None
_pool_lock = threading.Lock()

# 终态标志:True 表示进程已进入关停流程,禁止再惰性重建任何连接池。
_shutdown = False

_LLM_LIMITS = dict(max_keepalive_connections=20, max_connections=50)
_FEED_LIMITS = dict(max_keepalive_connections=10, max_connections=30)
_FEISHU_TIMEOUT_SECONDS = 10.0
# 建连超时的兜底默认值(settings 不可用时使用)。
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0


class HttpPoolShutdownError(RuntimeError):
    """连接池已进入关停终态后仍尝试获取 client。"""


def _connect_timeout(default: float = DEFAULT_CONNECT_TIMEOUT_SECONDS) -> float:
    try:
        return float(get_settings().http_connect_timeout_seconds)
    except Exception:  # pragma: no cover - 配置不可用时退回默认值
        return default


def _build_timeout(total_seconds: float) -> httpx.Timeout:
    """把标量超时拆成分阶段超时。

    connect 单独收紧(默认 5s),read/write/pool 沿用调用方给的整体预算,
    这样最坏耗时不再是 4 * total_seconds。
    """
    connect = min(_connect_timeout(), float(total_seconds))
    return httpx.Timeout(
        connect=connect,
        read=float(total_seconds),
        write=float(total_seconds),
        pool=float(total_seconds),
    )


def _ensure_not_shutdown() -> None:
    if _shutdown:
        raise HttpPoolShutdownError(
            "http connection pools have been shut down; refusing to lazily recreate them"
        )


def get_llm_client() -> httpx.Client:
    global _client
    _ensure_not_shutdown()
    if _client is None:
        with _pool_lock:
            _ensure_not_shutdown()
            if _client is None:
                s = get_settings()
                _client = httpx.Client(
                    timeout=_build_timeout(s.llm_timeout_seconds),
                    limits=httpx.Limits(**_LLM_LIMITS),
                    headers={"User-Agent": "news-caught/0.1"},
                )
    return _client


def get_async_llm_client() -> httpx.AsyncClient:
    """Shared AsyncClient for LLM calls (connection reuse across requests)."""
    global _async_client
    _ensure_not_shutdown()
    if _async_client is None:
        with _pool_lock:
            _ensure_not_shutdown()
            if _async_client is None:
                s = get_settings()
                _async_client = httpx.AsyncClient(
                    timeout=_build_timeout(s.llm_timeout_seconds),
                    limits=httpx.Limits(**_LLM_LIMITS),
                    headers={"User-Agent": "news-caught/0.1"},
                )
    return _async_client


def get_crawl_client() -> httpx.Client:
    """Shared client for article crawling (thread-safe, follows redirects)。

    超时改为读取 ``crawl_timeout_seconds``(此前硬编码 15.0)。
    """
    global _crawl_client
    _ensure_not_shutdown()
    if _crawl_client is None:
        with _pool_lock:
            _ensure_not_shutdown()
            if _crawl_client is None:
                try:
                    crawl_timeout = float(get_settings().crawl_timeout_seconds)
                except Exception:  # pragma: no cover - 配置不可用时退回历史默认值
                    crawl_timeout = 15.0
                _crawl_client = httpx.Client(
                    timeout=_build_timeout(crawl_timeout),
                    follow_redirects=True,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
                        )
                    },
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=30),
                )
    return _crawl_client


def get_feed_client() -> httpx.Client:
    """Shared client for news feed fetching (thread-safe, reuses TCP/TLS connections).

    超时与 UA 沿用统一的 http_timeout_seconds 配置;调用方不要在每次请求后 close,
    进程退出时由 close_llm_client() 统一回收。
    """
    global _feed_client
    _ensure_not_shutdown()
    if _feed_client is None:
        with _pool_lock:
            _ensure_not_shutdown()
            if _feed_client is None:
                s = get_settings()
                _feed_client = httpx.Client(
                    timeout=_build_timeout(s.http_timeout_seconds),
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
                        )
                    },
                    follow_redirects=True,
                    limits=httpx.Limits(**_FEED_LIMITS),
                )
    return _feed_client


def get_feishu_client() -> httpx.Client:
    """飞书消息发送专用共享 client（线程安全，跨 FeishuClient 实例复用连接）。

    构造时的超时只是兜底默认值；调用方（feishu_client.py）按需通过每请求
    timeout 参数覆盖，进程退出时由 close_llm_client() 统一回收。
    """
    global _feishu_client
    _ensure_not_shutdown()
    if _feishu_client is None:
        with _pool_lock:
            _ensure_not_shutdown()
            if _feishu_client is None:
                _feishu_client = httpx.Client(timeout=_build_timeout(_FEISHU_TIMEOUT_SECONDS))
    return _feishu_client


def close_llm_client() -> None:
    """关闭全部同步 client（保留惰性重建能力）。

    这是历史入口,语义不变:关闭之后再次调用 getter 会重建一个新的 client。
    真正的进程关停请用 :func:`shutdown_http_pools`。
    """
    global _client, _crawl_client, _feed_client, _feishu_client
    with _pool_lock:
        if _client is not None:
            _client.close()
            _client = None
        if _crawl_client is not None:
            _crawl_client.close()
            _crawl_client = None
        if _feed_client is not None:
            _feed_client.close()
            _feed_client = None
        if _feishu_client is not None:
            _feishu_client.close()
            _feishu_client = None


def shutdown_http_pools() -> None:
    """进程关停入口:关闭全部同步 client 并进入终态。

    终态之后任何 getter 都会抛 :class:`HttpPoolShutdownError`,避免关停后仍在
    运行的 daemon 线程静默重建连接池。
    """
    global _shutdown
    close_llm_client()
    with _pool_lock:
        _shutdown = True


def reset_http_pools() -> None:
    """退出终态并释放现有 client（仅供测试/重启场景使用）。"""
    global _shutdown
    with _pool_lock:
        _shutdown = False
    close_llm_client()


def is_shutdown() -> bool:
    return _shutdown


async def aclose_async_llm_client() -> None:
    global _async_client
    with _pool_lock:
        if _async_client is not None:
            await _async_client.aclose()
            _async_client = None
