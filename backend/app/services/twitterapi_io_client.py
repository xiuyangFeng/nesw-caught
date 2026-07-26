from __future__ import annotations

import json
import threading
import time

import httpx

from app.core.config import get_settings

_rate_limit_lock = threading.Lock()


class TwitterApiIoError(RuntimeError):
    pass


class TwitterApiIoClient:
    _last_request_started_at: float | None = None
    _last_probe_checked_at: float | None = None
    _last_probe_handle: str | None = None
    _last_probe_error: str | None = None
    _shared_client: httpx.Client | None = None

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.twitterapi_io_api_key)

    @classmethod
    def _get_shared_client(cls, timeout_seconds: float) -> httpx.Client:
        """进程级共享 client(httpx.Client 线程安全):跨请求复用 TCP/TLS 连接,
        不要按请求 close;测试通过类属性重置来替换底层 httpx.Client 实现。"""
        if cls._shared_client is None:
            cls._shared_client = httpx.Client(
                base_url="https://api.twitterapi.io",
                timeout=timeout_seconds,
            )
        return cls._shared_client

    @classmethod
    def close_shared_client(cls) -> None:
        client = cls._shared_client
        cls._shared_client = None
        close = getattr(client, "close", None)
        if callable(close):
            close()

    def _wait_for_rate_limit(self) -> None:
        min_interval_seconds = max(0.0, float(getattr(self.settings, "twitterapi_io_min_interval_seconds", 0.0)))
        if min_interval_seconds <= 0:
            return

        with _rate_limit_lock:
            last_request_started_at = self.__class__._last_request_started_at
            if last_request_started_at is None:
                self.__class__._last_request_started_at = time.monotonic()
                return

            elapsed = time.monotonic() - last_request_started_at
            remaining = min_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
            self.__class__._last_request_started_at = time.monotonic()

    def _probe_cache_ttl_seconds(self) -> float:
        min_interval_seconds = max(0.0, float(getattr(self.settings, "twitterapi_io_min_interval_seconds", 0.0)))
        return max(30.0, min_interval_seconds)

    def _request(self, path: str, params: dict[str, object], *, apply_rate_limit: bool = True) -> dict[str, object]:
        if not self.configured:
            raise TwitterApiIoError("twitterapi.io api key is not configured")

        if apply_rate_limit:
            self._wait_for_rate_limit()

        try:
            client = self._get_shared_client(float(self.settings.twitterapi_io_timeout_seconds))
            response = client.get(
                path,
                headers={"X-API-Key": str(self.settings.twitterapi_io_api_key)},
                params=params,
            )
        except httpx.TimeoutException as exc:
            raise TwitterApiIoError("twitterapi.io request timed out") from exc
        except httpx.HTTPError as exc:
            raise TwitterApiIoError(f"twitterapi.io request failed: {exc}") from exc

        if response.status_code >= 400:
            raise TwitterApiIoError(f"twitterapi.io request failed with status {response.status_code}")

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise TwitterApiIoError("twitterapi.io returned invalid json") from exc

        if not isinstance(payload, dict):
            raise TwitterApiIoError("twitterapi.io returned an invalid payload")

        return payload

    def get_user_last_tweets(self, handle: str, limit: int = 20, *, apply_rate_limit: bool = True) -> list[dict[str, object]]:
        payload = self._request(
            "/twitter/user/last_tweets",
            {
                "userName": handle.lstrip("@"),
                "includeReplies": False,
                "limit": limit,
            },
            apply_rate_limit=apply_rate_limit,
        )
        rows = payload.get("tweets")
        if not isinstance(rows, list):
            data = payload.get("data")
            if isinstance(data, dict):
                rows = data.get("tweets")
        if not isinstance(rows, list):
            raise TwitterApiIoError("twitterapi.io last_tweets response missing tweets")
        return [item for item in rows[:limit] if isinstance(item, dict)]

    def advanced_search(self, query: str, limit: int = 20) -> list[dict[str, object]]:
        payload = self._request(
            "/twitter/tweet/advanced_search",
            {
                "query": query,
                "queryType": "Latest",
                "limit": limit,
            },
        )
        rows = payload.get("tweets")
        if not isinstance(rows, list):
            data = payload.get("data")
            if isinstance(data, dict):
                rows = data.get("tweets")
        if not isinstance(rows, list):
            raise TwitterApiIoError("twitterapi.io advanced_search response missing tweets")
        return [item for item in rows[:limit] if isinstance(item, dict)]

    def probe_account(self, handle: str) -> None:
        normalized_handle = handle.lstrip("@")
        now = time.monotonic()
        cache_ttl = self._probe_cache_ttl_seconds()
        last_probe_checked_at = self.__class__._last_probe_checked_at
        if (
            last_probe_checked_at is not None
            and self.__class__._last_probe_handle == normalized_handle
            and now - last_probe_checked_at < cache_ttl
        ):
            if self.__class__._last_probe_error:
                raise TwitterApiIoError(self.__class__._last_probe_error)
            return

        try:
            self.get_user_last_tweets(normalized_handle, limit=1, apply_rate_limit=False)
        except TwitterApiIoError as exc:
            self.__class__._last_probe_checked_at = now
            self.__class__._last_probe_handle = normalized_handle
            self.__class__._last_probe_error = str(exc)
            raise

        self.__class__._last_probe_checked_at = now
        self.__class__._last_probe_handle = normalized_handle
        self.__class__._last_probe_error = None
