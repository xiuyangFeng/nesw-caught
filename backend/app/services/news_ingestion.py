from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import time
from typing import Literal
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.repositories.source_health_repository import SourceHealthRepository
from app.services.http_client import HttpClientFactory

SourceType = Literal["rss", "html"]


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    source_type: SourceType
    url: str
    market: str
    language: str | None = None
    parser: str = "rss"
    item_limit: int = 20
    entry_selector: str | None = None
    title_selector: str | None = None
    link_selector: str | None = None
    time_selector: str | None = None
    content_selector: str | None = None
    disabled: bool = False


@dataclass(frozen=True)
class SourceItem:
    title: str
    canonical_url: str
    summary: str | None
    content_text: str | None
    published_at: datetime | None


@dataclass(frozen=True)
class SourceFetchResult:
    source_name: str
    source_type: str
    status: str
    fetched_count: int
    inserted_count: int
    error: str | None
    latency_ms: float


@dataclass(frozen=True)
class RefreshSummary:
    started_at: datetime
    finished_at: datetime
    fetched_count: int
    inserted_count: int
    results: list[SourceFetchResult]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_feed_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None

    try:
        return _normalize_datetime(parsedate_to_datetime(raw))
    except (TypeError, ValueError):
        pass

    normalized = raw.replace("Z", "+00:00")
    try:
        return _normalize_datetime(datetime.fromisoformat(normalized))
    except ValueError:
        return None


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    soup = BeautifulSoup(value, "html.parser")
    text = soup.get_text(" ", strip=True)
    return text or None


def _canonicalize_url(url: str, base_url: str) -> str:
    return urljoin(base_url, url.strip())


def _content_from_entry(entry: ET.Element) -> str | None:
    for tag_name in ("content", "summary", "description"):
        for node in entry.findall(f".//{{*}}{tag_name}"):
            if node.text:
                cleaned = _clean_text(node.text)
                if cleaned:
                    return cleaned
    return None


def _parse_rss_or_atom(content: str, source: SourceDefinition) -> list[SourceItem]:
    root = ET.fromstring(content)
    entries = root.findall(".//item")
    is_atom = False
    if not entries:
        entries = root.findall(".//{*}entry")
        is_atom = True

    items: list[SourceItem] = []
    for entry in entries[: source.item_limit]:
        title = entry.findtext("title") or entry.findtext("{*}title")
        if not title:
            continue

        raw_link = entry.findtext("link")
        if is_atom and not raw_link:
            link_node = entry.find("{*}link[@rel='alternate']") or entry.find("{*}link")
            raw_link = (link_node.attrib.get("href") if link_node is not None else None)
        if not raw_link:
            continue

        published_at = _parse_feed_datetime(
            entry.findtext("pubDate")
            or entry.findtext("{*}published")
            or entry.findtext("{*}updated")
            or entry.findtext("{*}dc:date")
        )
        content_text = _content_from_entry(entry)
        summary = content_text[:280] if content_text else None
        items.append(
            SourceItem(
                title=_clean_text(title) or title.strip(),
                canonical_url=_canonicalize_url(raw_link, source.url),
                summary=summary,
                content_text=content_text,
                published_at=published_at,
            )
        )
    return items


def _parse_selector_html(content: str, source: SourceDefinition) -> list[SourceItem]:
    if not source.entry_selector or not source.title_selector or not source.link_selector:
        raise ValueError(f"html source {source.name} is missing selectors")

    soup = BeautifulSoup(content, "html.parser")
    items: list[SourceItem] = []
    seen_urls: set[str] = set()
    for entry in soup.select(source.entry_selector)[: source.item_limit]:
        title_node = entry.select_one(source.title_selector)
        link_node = entry.select_one(source.link_selector)
        if title_node is None or link_node is None:
            continue

        title = title_node.get_text(" ", strip=True)
        href = link_node.get("href")
        if not title or not href:
            continue

        time_node = entry.select_one(source.time_selector) if source.time_selector else None
        published_at = None
        if time_node is not None:
            time_text = time_node.get_text(" ", strip=True)
            day = _utc_now().date().isoformat()
            published_at = _parse_feed_datetime(f"{day} {time_text}+08:00")

        content_node = entry.select_one(source.content_selector) if source.content_selector else title_node
        content_text = content_node.get_text(" ", strip=True) if content_node is not None else None
        canonical_url = _canonicalize_url(href, source.url)
        if canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)
        items.append(
            SourceItem(
                title=title,
                canonical_url=canonical_url,
                summary=(content_text[:280] if content_text else None),
                content_text=content_text,
                published_at=published_at,
            )
        )
    return items


def _extract_json_array(content: str, marker: str) -> str | None:
    marker_index = content.find(marker)
    if marker_index == -1:
        return None

    array_start = content.find("[", marker_index)
    if array_start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(array_start, len(content)):
        char = content[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return content[array_start : index + 1]
    return None


def _parse_anchor_list_html(content: str, source: SourceDefinition) -> list[SourceItem]:
    if not source.entry_selector:
        raise ValueError(f"html source {source.name} is missing entry selector")

    soup = BeautifulSoup(content, "html.parser")
    items: list[SourceItem] = []
    seen_urls: set[str] = set()
    for link_node in soup.select(source.entry_selector):
        href = link_node.get("href")
        title = link_node.get_text(" ", strip=True)
        if not href or not title:
            continue
        canonical_url = _canonicalize_url(href, source.url)
        if canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)
        items.append(
            SourceItem(
                title=title,
                canonical_url=canonical_url,
                summary=None,
                content_text=None,
                published_at=None,
            )
        )
        if len(items) >= source.item_limit:
            break
    return items


def _parse_zhipu_news_inline_json(content: str, source: SourceDefinition) -> list[SourceItem]:
    start_marker = 'newsItems\\":['
    start_index = content.find(start_marker)
    if start_index == -1:
        start_marker = "newsItems"
        start_index = content.find(start_marker)
    if start_index == -1:
        raise ValueError("zhipu newsItems payload not found")

    array_start = content.find("[", start_index)
    array_end = content.find('],\\"locale\\":', array_start)
    if array_start == -1:
        raise ValueError("zhipu newsItems payload not found")

    if array_end != -1:
        raw_array = content[array_start : array_end + 1]
    else:
        raw_array = _extract_json_array(content, start_marker)
    if not raw_array:
        raise ValueError("zhipu newsItems payload not found")

    normalized = raw_array.replace('\\"', '"').replace("\\/", "/")
    records = json.loads(normalized)
    items: list[SourceItem] = []
    for record in records[: source.item_limit]:
        item_id = record.get("id")
        title = record.get("title_zh") or record.get("title_en")
        if not item_id or not title:
            continue

        summary = _clean_text(record.get("resume_zh") or record.get("resume_en"))
        published_at = _parse_feed_datetime(record.get("createAt"))
        items.append(
            SourceItem(
                title=title.strip(),
                canonical_url=_canonicalize_url(f"/zh/news/{item_id}", source.url),
                summary=summary[:280] if summary else None,
                content_text=summary,
                published_at=published_at,
            )
        )
    return items


def _default_sources() -> list[SourceDefinition]:
    return [
        SourceDefinition(
            name="WSJ World News",
            source_type="rss",
            url="https://feeds.a.dj.com/rss/RSSWorldNews.xml",
            market="us",
            language="en",
        ),
        SourceDefinition(
            name="The Verge",
            source_type="rss",
            url="https://www.theverge.com/rss/index.xml",
            market="us",
            language="en",
        ),
        SourceDefinition(
            name="36Kr",
            source_type="rss",
            url="https://36kr.com/feed",
            market="cn",
            language="zh",
        ),
        SourceDefinition(
            name="SEC Press Releases",
            source_type="rss",
            url="https://www.sec.gov/news/pressreleases.rss",
            market="us",
            language="en",
        ),
        SourceDefinition(
            name="CLS Telegraph",
            source_type="html",
            url="https://www.cls.cn/telegraph",
            market="cn",
            language="zh",
            parser="selector_html",
            entry_selector="div.p-t-20.p-b-20.b-b-w-1",
            title_selector=".telegraph-content-box .c-34304b",
            link_selector="a[href^='/detail/']",
            time_selector=".telegraph-time-box",
            content_selector=".telegraph-content-box .c-34304b",
        ),
        SourceDefinition(
            name="MiniMax News",
            source_type="html",
            url="https://www.minimaxi.com/news",
            market="hk",
            language="zh",
            parser="anchor_list_html",
            entry_selector="a[href^='/news/']",
            item_limit=20,
        ),
        SourceDefinition(
            name="Zhipu AI News",
            source_type="html",
            url="https://www.zhipuai.cn/zh/news",
            market="cn",
            language="zh",
            parser="zhipu_news_inline_json",
            item_limit=20,
        ),
    ]


def load_sources() -> list[SourceDefinition]:
    settings = get_settings()
    sources = _default_sources()
    if not settings.news_sources_file:
        return sources

    try:
        with open(settings.news_sources_file, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return sources

    extras = payload.get("sources", []) if isinstance(payload, dict) else []
    for raw in extras:
        sources.append(SourceDefinition(**raw))
    return sources


class NewsIngestionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.source_health_repository = SourceHealthRepository(session)

    def refresh_all(self) -> RefreshSummary:
        started_at = _utc_now()
        fetched_count = 0
        inserted_count = 0
        results: list[SourceFetchResult] = []

        for source in load_sources():
            if source.disabled:
                continue
            result = self._refresh_source(source)
            fetched_count += result.fetched_count
            inserted_count += result.inserted_count
            results.append(result)

        finished_at = _utc_now()
        return RefreshSummary(
            started_at=started_at,
            finished_at=finished_at,
            fetched_count=fetched_count,
            inserted_count=inserted_count,
            results=results,
        )

    def _refresh_source(self, source: SourceDefinition) -> SourceFetchResult:
        started = time.perf_counter()
        health = self.source_health_repository.get_or_create(
            source_name=source.name,
            source_type=source.source_type,
        )
        health.total_fetches += 1

        try:
            with HttpClientFactory().create() as client:
                response = client.get(source.url)
            response.raise_for_status()
            if source.source_type == "rss":
                items = _parse_rss_or_atom(response.text, source)
            elif source.parser == "anchor_list_html":
                items = _parse_anchor_list_html(response.text, source)
            elif source.parser == "zhipu_news_inline_json":
                items = _parse_zhipu_news_inline_json(response.text, source)
            elif source.parser == "selector_html":
                items = _parse_selector_html(response.text, source)
            else:
                raise ValueError(f"unsupported parser for source {source.name}: {source.parser}")

            inserted_count = 0
            for item in items:
                inserted_count += self._persist_item(source, item)

            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            health.last_success_at = _utc_now()
            health.consecutive_failures = 0
            health.avg_latency_ms = (
                latency_ms
                if health.avg_latency_ms is None
                else round((health.avg_latency_ms + latency_ms) / 2, 2)
            )
            self.session.commit()
            return SourceFetchResult(
                source_name=source.name,
                source_type=source.source_type,
                status="ok",
                fetched_count=len(items),
                inserted_count=inserted_count,
                error=None,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            self.session.rollback()
            health = self.source_health_repository.get_or_create(
                source_name=source.name,
                source_type=source.source_type,
            )
            health.last_failure_at = _utc_now()
            health.total_failures += 1
            health.consecutive_failures += 1
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            self.session.commit()
            return SourceFetchResult(
                source_name=source.name,
                source_type=source.source_type,
                status="error",
                fetched_count=0,
                inserted_count=0,
                error=str(exc),
                latency_ms=latency_ms,
            )

    def _persist_item(self, source: SourceDefinition, item: SourceItem) -> int:
        canonical_url = item.canonical_url
        url_hash = sha256(canonical_url.encode("utf-8")).hexdigest()
        existing = self.session.scalar(select(NewsItem.id).where(NewsItem.url_hash == url_hash))
        if existing is not None:
            return 0

        news_item = NewsItem(
            source_name=source.name,
            source_url=source.url,
            title=item.title[:500],
            summary=item.summary,
            canonical_url=canonical_url,
            url_hash=url_hash,
            market=source.market,
            language=source.language,
            sentiment_label=None,
            sentiment_score=None,
            published_at=item.published_at,
            fetched_at=_utc_now(),
            ingest_status="ingested",
        )
        self.session.add(news_item)
        self.session.flush()
        if item.content_text:
            self.session.add(
                ArticleContent(
                    news_id=news_item.id,
                    content_text=item.content_text,
                    content_html=None,
                    extract_status="success",
                    extract_error=None,
                    extracted_at=_utc_now(),
                )
            )
        return 1
