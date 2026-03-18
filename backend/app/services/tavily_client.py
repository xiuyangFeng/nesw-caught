from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

from app.services.news_ingestion import SourceItem, _parse_feed_datetime

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


@dataclass(frozen=True)
class TavilySearchResult:
    title: str
    url: str
    content: str | None
    published_date: str | None
    score: float


class TavilyClientError(RuntimeError):
    pass


class TavilyClient:
    def __init__(self, api_key: str, *, timeout: float = 15.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def search_news(self, query: str, *, max_results: int = 5) -> list[SourceItem]:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    TAVILY_SEARCH_URL,
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": "basic",
                        "topic": "news",
                        "max_results": max_results,
                        "include_answer": False,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TavilyClientError(f"tavily request failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise TavilyClientError("tavily returned invalid json") from exc

        results = payload.get("results", [])
        items: list[SourceItem] = []
        for r in results:
            title = r.get("title")
            url = r.get("url")
            if not title or not url:
                continue
            content = r.get("content")
            published_at = _parse_feed_datetime(r.get("published_date"))
            items.append(
                SourceItem(
                    title=title.strip(),
                    canonical_url=url.strip(),
                    summary=content[:280] if content else None,
                    content_text=content,
                    published_at=published_at,
                )
            )
        return items
