import httpx

from app.core.config import get_settings

_client: httpx.Client | None = None
_async_client: httpx.AsyncClient | None = None
_crawl_client: httpx.Client | None = None
_feed_client: httpx.Client | None = None

_LLM_LIMITS = dict(max_keepalive_connections=20, max_connections=50)
_FEED_LIMITS = dict(max_keepalive_connections=10, max_connections=30)


def get_llm_client() -> httpx.Client:
    global _client
    if _client is None:
        s = get_settings()
        _client = httpx.Client(
            timeout=s.llm_timeout_seconds,
            limits=httpx.Limits(**_LLM_LIMITS),
            headers={"User-Agent": "news-caught/0.1"},
        )
    return _client


def get_async_llm_client() -> httpx.AsyncClient:
    """Shared AsyncClient for LLM calls (connection reuse across requests)."""
    global _async_client
    if _async_client is None:
        s = get_settings()
        _async_client = httpx.AsyncClient(
            timeout=s.llm_timeout_seconds,
            limits=httpx.Limits(**_LLM_LIMITS),
            headers={"User-Agent": "news-caught/0.1"},
        )
    return _async_client


def get_crawl_client() -> httpx.Client:
    """Shared client for article crawling (thread-safe, follows redirects)."""
    global _crawl_client
    if _crawl_client is None:
        _crawl_client = httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=30),
        )
    return _crawl_client


def get_feed_client() -> httpx.Client:
    """Shared client for news feed fetching (thread-safe, reuses TCP/TLS connections).

    超时与 UA 与 HttpClientFactory 保持一致;调用方不要在每次请求后 close,
    进程退出时由 close_llm_client() 统一回收。
    """
    global _feed_client
    if _feed_client is None:
        s = get_settings()
        _feed_client = httpx.Client(
            timeout=s.http_timeout_seconds,
            headers={"User-Agent": "news-caught/0.1"},
            follow_redirects=True,
            limits=httpx.Limits(**_FEED_LIMITS),
        )
    return _feed_client


def close_llm_client() -> None:
    global _client, _crawl_client, _feed_client
    if _client is not None:
        _client.close()
        _client = None
    if _crawl_client is not None:
        _crawl_client.close()
        _crawl_client = None
    if _feed_client is not None:
        _feed_client.close()
        _feed_client = None


async def aclose_async_llm_client() -> None:
    global _async_client
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None
