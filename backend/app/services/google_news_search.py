from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from app.services import http_pool
from app.services.news_ingestion import SourceItem, _clean_text, _parse_feed_datetime

GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search"


class GoogleNewsSearchError(RuntimeError):
    pass


def _build_google_news_url(query: str, *, language: str = "en") -> str:
    from urllib.parse import quote_plus

    encoded = quote_plus(query)
    lang_lower = language.lower()
    if lang_lower in ("zh-hk", "hk"):
        return f"{GOOGLE_NEWS_RSS_BASE}?q={encoded}&hl=zh-HK&gl=HK&ceid=HK:zh-Hant"
    if lang_lower in ("zh-tw", "tw"):
        return f"{GOOGLE_NEWS_RSS_BASE}?q={encoded}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    if lang_lower.startswith("zh"):
        return f"{GOOGLE_NEWS_RSS_BASE}?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    return f"{GOOGLE_NEWS_RSS_BASE}?q={encoded}&hl=en&gl=US&ceid=US:en"


class GoogleNewsSearchClient:
    def __init__(self, *, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def search_news(
        self,
        query: str,
        *,
        max_results: int = 8,
        language: str = "en",
    ) -> list[SourceItem]:
        url = _build_google_news_url(query, language=language)
        try:
            # 复用 http_pool 的共享 feed client（线程安全，自动跟随重定向），
            # 不再每次新建连接；每请求 timeout 覆盖保留自定义超时行为。
            client = http_pool.get_feed_client()
            response = client.get(url, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise GoogleNewsSearchError(f"google news rss request failed: {exc}") from exc

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise GoogleNewsSearchError(f"google news rss parse error: {exc}") from exc

        items: list[SourceItem] = []
        for entry in root.findall(".//item")[:max_results]:
            title_raw = entry.findtext("title")
            link = entry.findtext("link")
            if not title_raw or not link:
                continue
            title = _clean_text(title_raw) or title_raw.strip()
            pub_date = _parse_feed_datetime(entry.findtext("pubDate"))
            description = _clean_text(entry.findtext("description"))
            items.append(
                SourceItem(
                    title=title,
                    canonical_url=link.strip(),
                    summary=description[:280] if description else None,
                    content_text=description,
                    published_at=pub_date,
                )
            )
        return items
