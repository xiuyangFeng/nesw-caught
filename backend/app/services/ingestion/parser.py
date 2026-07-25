from __future__ import annotations

import html
from datetime import UTC, datetime
import json
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from app.services.ingestion.types import SourceDefinition, SourceItem
from app.services.ingestion.utils import (
    _canonicalize_url,
    _clean_text,
    _parse_feed_datetime,
    _utc_now,
)

# ElementTree treats "{*}dc:date" as local name "dc:date" (never matches).
# Dublin Core date uses Clark notation or a wildcard local-name "date".
_DC_DATE = "{http://purl.org/dc/elements/1.1/}date"


def _entry_published_text(entry: ET.Element) -> str | None:
    return (
        entry.findtext("pubDate")
        or entry.findtext("{*}published")
        or entry.findtext("{*}updated")
        or entry.findtext(_DC_DATE)
        or entry.findtext("{*}date")
    )


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

        published_at = _parse_feed_datetime(_entry_published_text(entry), market=source.market)
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
                content_html=None,
                published_at=None,
            )
        )
        if len(items) >= source.item_limit:
            break
    return items


def _decode_next_data_chunks(content: str) -> list[str]:
    pattern = re.compile(r'self\.__next_f\.push\(\[1,"((?:\\.|[^"\\])*)"\]\)', re.DOTALL)
    chunks: list[str] = []
    for raw in pattern.findall(content):
        try:
            chunks.append(json.loads(f'"{raw}"'))
        except json.JSONDecodeError:
            continue
    return chunks


def _parse_minimax_detail_html(
    content: str,
    source: SourceDefinition,
    *,
    canonical_url: str,
    fallback_title: str,
) -> SourceItem:
    del source
    normalized_content = (
        content
        .replace("\\u003c", "<")
        .replace("\\u003e", ">")
        .replace("\\u0026", "&")
        .replace('\\"', '"')
        .replace("\\/", "/")
    )

    title_match = re.search(
        r'ArticleTitle","props":\{"date":"(?P<date>\d{4}-\d{2}-\d{2})","title":"(?P<title>[^"]+)"\}',
        normalized_content,
    )
    published_at = _parse_feed_datetime(f"{title_match.group('date')}T00:00:00+00:00") if title_match else None
    title = title_match.group("title") if title_match else fallback_title

    content_html = None
    raw_body_marker = 'self.__next_f.push([1,"\\u003cdiv style=\\"margin: 0; padding: 40px 20px;'
    raw_body_start = content.find(raw_body_marker)
    if raw_body_start != -1:
        raw_body_end = content.find('"])</script>', raw_body_start)
        raw_body = content[raw_body_start + len('self.__next_f.push([1,"') : raw_body_end]
        content_html = (
            raw_body
            .replace("\\u003c", "<")
            .replace("\\u003e", ">")
            .replace("\\u0026", "&")
            .replace('\\"', '"')
            .replace("\\/", "/")
            .strip()
        )
    else:
        body_match = None
        for pattern in (
            r'(<div[^>]*max-width:\s*768px;[^>]*>[\s\S]*?</div>)',
            r'(<div[^>]*>[\s\S]*?今天，我们介绍MiniMax[\s\S]*?</div>)',
        ):
            body_match = re.search(pattern, normalized_content)
            if body_match:
                break
        content_html = html.unescape(body_match.group(1)).strip() if body_match else None
    content_text = _clean_text(content_html) if content_html else None
    if not content_text:
        text_match = re.search(r"(今天，我们介绍MiniMax[\s\S]+?)(?:欢迎使用[\s\S]+?！)", content)
        if text_match:
            content_text = _clean_text(text_match.group(0))

    if not published_at and not content_text:
        raise ValueError(f"minimax detail payload not found for {canonical_url}")

    return SourceItem(
        title=title,
        canonical_url=canonical_url,
        summary=(content_text[:280] if content_text else None),
        content_text=content_text,
        content_html=content_html,
        published_at=published_at,
    )


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
        published_at = _parse_feed_datetime(record.get("createAt"), market=source.market)
        items.append(
            SourceItem(
                title=title.strip(),
                canonical_url=_canonicalize_url(f"/zh/news/{item_id}", source.url),
                summary=summary[:280] if summary else None,
                content_text=summary,
                content_html=None,
                published_at=published_at,
            )
        )
    return items


def _parse_wallstreetcn_live_json(content: str, source: SourceDefinition) -> list[SourceItem]:
    payload = json.loads(content)
    records = payload.get("data", {}).get("items", [])
    if not isinstance(records, list):
        raise ValueError("wallstreetcn live payload is missing data.items array")

    items: list[SourceItem] = []
    for record in records[: source.item_limit]:
        if not isinstance(record, dict):
            continue
        item_id = record.get("id")
        uri = record.get("uri")
        if not item_id or not uri:
            continue

        content_text = _clean_text(record.get("content_text"))
        raw_title = (record.get("title") or "").strip()
        if raw_title:
            title = raw_title
        elif content_text:
            title = content_text[:60]
        else:
            continue

        display_time = record.get("display_time")
        published_at = (
            datetime.fromtimestamp(display_time, tz=UTC)
            if isinstance(display_time, (int, float)) and not isinstance(display_time, bool)
            else None
        )

        items.append(
            SourceItem(
                title=title,
                canonical_url=_canonicalize_url(uri, source.url),
                summary=content_text[:280] if content_text else None,
                content_text=content_text,
                content_html=record.get("content"),
                published_at=published_at,
            )
        )
    return items


def _parse_the_news_api_json(content: str, source: SourceDefinition) -> list[SourceItem]:
    payload = json.loads(content)
    records = payload.get("data", [])
    if not isinstance(records, list):
        raise ValueError("the news api payload is missing data array")

    items: list[SourceItem] = []
    for record in records[: source.item_limit]:
        if not isinstance(record, dict):
            continue

        title = record.get("title")
        canonical_url = record.get("url")
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(canonical_url, str) or not canonical_url.strip():
            continue

        summary = _clean_text(record.get("description"))
        content_text = _clean_text(record.get("snippet")) or summary
        items.append(
            SourceItem(
                title=title.strip(),
                canonical_url=canonical_url.strip(),
                summary=summary[:280] if summary else None,
                content_text=content_text,
                content_html=None,
                published_at=_parse_feed_datetime(record.get("published_at"), market=source.market),
            )
        )
    return items
