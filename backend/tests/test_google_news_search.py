from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from app.services.google_news_search import GoogleNewsSearchClient, GoogleNewsSearchError

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<item>
<title>Sample Headline</title>
<link>https://example.com/a</link>
<pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
<description>Sample description</description>
</item>
</channel>
</rss>"""


def test_search_news_reuses_shared_feed_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """search_news 不应每次新建 httpx.Client，而应复用 http_pool 的共享 feed client。"""
    calls: list[tuple[str, float | None]] = []

    class _FakeFeedClient:
        def get(self, url: str, *, timeout: float | None = None):
            calls.append((url, timeout))
            resp = MagicMock()
            resp.text = SAMPLE_RSS
            resp.raise_for_status = MagicMock()
            return resp

    fake_client = _FakeFeedClient()
    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: fake_client)

    client = GoogleNewsSearchClient(timeout=7.5)
    items = client.search_news("apple", max_results=5, language="en")

    assert len(calls) == 1
    # 每次请求的 timeout 覆盖仍要保留调用方传入的自定义超时
    assert calls[0][1] == 7.5
    assert len(items) == 1
    assert items[0].title == "Sample Headline"
    assert items[0].canonical_url == "https://example.com/a"


def test_search_news_wraps_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingFeedClient:
        def get(self, url: str, *, timeout: float | None = None):
            raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

    monkeypatch.setattr("app.services.http_pool.get_feed_client", lambda: _FailingFeedClient())

    client = GoogleNewsSearchClient()
    with pytest.raises(GoogleNewsSearchError):
        client.search_news("apple")
