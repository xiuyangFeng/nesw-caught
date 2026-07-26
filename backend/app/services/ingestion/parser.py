from __future__ import annotations

import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from app.services.ingestion.types import SourceDefinition, SourceItem
from app.services.ingestion.utils import (
    _canonicalize_url,
    _clean_text,
    _parse_feed_datetime,
    _parse_list_time_text,
)

# ElementTree treats "{*}dc:date" as local name "dc:date" (never matches).
# Dublin Core date uses Clark notation or a wildcard local-name "date".
_DC_DATE = "{http://purl.org/dc/elements/1.1/}date"
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

logger = logging.getLogger(__name__)

try:
    import lxml  # noqa: F401
    _BS4_PARSER = "lxml"
except ImportError:
    _BS4_PARSER = "html.parser"


def _clean_xml_content(content: str) -> str:
    if not content:
        return ""
    return _CONTROL_CHAR_RE.sub("", content)


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
    cleaned_content = _clean_xml_content(content)
    try:
        root = ET.fromstring(cleaned_content)
    except ET.ParseError:
        # 尝试清洗更多可能引起 XML 错误的未转义 & 符号后再解
        sanitized = re.sub(r"&(?!amp;|lt;|gt;|apos;|quot;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", cleaned_content)
        root = ET.fromstring(sanitized)

    entries = root.findall(".//item")
    is_atom = False
    if not entries:
        entries = root.findall(".//{*}entry")
        is_atom = True

    items: list[SourceItem] = []
    seen_urls: set[str] = set()

    for entry in entries:
        title = entry.findtext("title") or entry.findtext("{*}title")
        if not title:
            continue

        raw_link = entry.findtext("link")
        if is_atom and not raw_link:
            # 必须显式判 `is not None`：ElementTree 的 Element.__bool__ 判的是「有没有子元素」，
            # 而 Atom 的 <link/> 是自闭合空元素 → 恒为 False，用 `or` 会永远退化成
            # 「文档里第一个 link」；当 feed 把 rel="self"/"edit" 排在 alternate 之前时，
            # canonical_url 会指向错误地址（Python 3.12+ 还会给出 DeprecationWarning）。
            link_node = entry.find("{*}link[@rel='alternate']")
            if link_node is None:
                link_node = entry.find("{*}link")
            raw_link = (link_node.attrib.get("href") if link_node is not None else None)
        if not raw_link:
            continue

        canonical_url = _canonicalize_url(raw_link, source.url)
        if canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)

        published_at = _parse_feed_datetime(_entry_published_text(entry), market=source.market)
        content_text = _content_from_entry(entry)
        summary = content_text[:280] if content_text else None
        items.append(
            SourceItem(
                title=_clean_text(title) or title.strip(),
                canonical_url=canonical_url,
                summary=summary,
                content_text=content_text,
                published_at=published_at,
            )
        )
        if len(items) >= source.item_limit:
            break
    return items


def _parse_selector_html(content: str, source: SourceDefinition) -> list[SourceItem]:
    if not source.entry_selector or not source.title_selector or not source.link_selector:
        raise ValueError(f"html source {source.name} is missing selectors")

    soup = BeautifulSoup(content, _BS4_PARSER)
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
            # 时区由 source.market 推导（旧实现硬编码 +08:00，任何非中国源都会被误当北京时间），
            # 裸时钟按本地当天日期补齐并做跨日回退，详见 _parse_list_time_text。
            published_at = _parse_list_time_text(time_text, market=source.market)

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

    soup = BeautifulSoup(content, _BS4_PARSER)
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


def _zhipu_payload_candidates(content: str) -> list[str]:
    """按可信度排列的候选文本：先是解转义后的 RSC 流式载荷，再退回原始 HTML。

    智谱新闻页是 Next.js 的 RSC 流式载荷（`self.__next_f.push([1,"..."])`），
    真正的 JSON 被当作 **JSON 字符串字面量** 嵌在 push 调用里，页面上看到的是
    `\\"newsItems\\":[` 这种多层转义。正确的解转义方式是让 json 自己做
    （`json.loads('"' + escaped + '"')`，即 `_decode_next_data_chunks` 的做法），
    而不是 `str.replace('\\"', '"')` —— 后者遇到正文字段里本身含 `\\"` 的记录
    就会把结构打碎（线上表现为 `Expecting ',' delimiter: char 221183`）。
    载荷可能被切成多个 push 分块，这里拼接后再定位。
    """
    candidates: list[str] = []
    chunks = _decode_next_data_chunks(content)
    if chunks:
        candidates.append("".join(chunks))
    candidates.append(content)
    return candidates


def _load_json_array(raw_array: str | None) -> list | None:
    if not raw_array:
        return None
    try:
        parsed = json.loads(raw_array)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


def _parse_zhipu_news_inline_json(content: str, source: SourceDefinition) -> list[SourceItem]:
    """智谱新闻页内联 JSON 解析器。

    数组边界一律用 `_extract_json_array` 的**括号配平扫描**定位（正确处理字符串态
    与反斜杠转义），不再依赖 `],\\"locale\\":` 这类固定尾部标记 —— 该标记随页面改版
    早已失效，且在页面后半段还能"误命中"，把数组一路吃到 30 万字符外。
    """
    records: list | None = None
    for text in _zhipu_payload_candidates(content):
        for marker in ('"newsItems"', "newsItems"):
            records = _load_json_array(_extract_json_array(text, marker))
            if records is not None:
                break
        if records is not None:
            break

    if records is None:
        raise ValueError("zhipu newsItems payload not found")

    items: list[SourceItem] = []
    seen_urls: set[str] = set()
    for record in records:
        if len(items) >= source.item_limit:
            break
        # 单条降级：字段畸形只跳过该条，不让整批解析失败
        if not isinstance(record, dict):
            continue

        item_id = record.get("id")
        if isinstance(item_id, bool) or not isinstance(item_id, (int, str)):
            continue
        item_id = str(item_id).strip()
        if not item_id:
            continue

        title_value = record.get("title_zh") or record.get("title_en")
        if not isinstance(title_value, str) or not title_value.strip():
            continue
        title = title_value.strip()

        summary = _clean_text(record.get("resume_zh") if isinstance(record.get("resume_zh"), str) else None)
        if not summary:
            summary = _clean_text(record.get("resume_en") if isinstance(record.get("resume_en"), str) else None)

        created_at = record.get("createAt")
        published_at = _parse_feed_datetime(
            created_at if isinstance(created_at, str) else None, market=source.market
        )

        canonical_url = _canonicalize_url(f"/zh/news/{item_id}", source.url)
        if canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)

        items.append(
            SourceItem(
                title=title,
                canonical_url=canonical_url,
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
        if not item_id or not isinstance(uri, str) or not uri.strip():
            continue

        content_text = _clean_text(record.get("content_text"))
        title_value = record.get("title")
        raw_title = title_value.strip() if isinstance(title_value, str) else ""
        if raw_title:
            title = raw_title
        elif content_text:
            title = content_text[:60]
        else:
            continue

        display_time = record.get("display_time")
        published_at = None
        if isinstance(display_time, (int, float)) and not isinstance(display_time, bool):
            try:
                published_at = datetime.fromtimestamp(display_time, tz=UTC)
            except (ValueError, OverflowError, OSError):
                published_at = None

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


def _epoch_to_utc(value: object) -> datetime | None:
    """把 epoch 秒（int/float，排除 bool）转成 UTC datetime；越界或类型不符返回 None。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (ValueError, OverflowError, OSError):
        return None


def _cls_title_from_body(body: str | None) -> str | None:
    """快讯 title 为空时的回退：优先取 `【...】` 方括号内的标题，否则截取正文开头。"""
    if not body:
        return None
    bracket = re.match(r"^\s*[【\[]([^】\]]{2,80})[】\]]", body)
    if bracket:
        title = bracket.group(1).strip()
        if title:
            return title
    return body.strip()[:60] or None


def _parse_cls_telegraph_json(content: str, source: SourceDefinition) -> list[SourceItem]:
    """财联社 7x24 快讯官方 JSON（/v1/roll/get_roll_list）解析器。

    背景：cls.cn/telegraph 已改为 Next.js SSR 空壳，`__NEXT_DATA__` 里不含任何新闻数据，
    原先的 `.telegraph-content-box` / `.telegraph-time-box` 选择器命中数为 0，该源产出归零。
    改走官方 JSON 接口（签名与 Referer 由 fetcher 构造）。

    健壮性：errno != 0、data/roll_data 缺失、单条字段畸形都只做局部降级，
    不让整批抓取失败（与 wallstreetcn 解析器保持一致的风格）。
    """
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("cls telegraph payload is not a JSON object")

    errno = payload.get("errno")
    if isinstance(errno, (int, float)) and not isinstance(errno, bool) and int(errno) != 0:
        # 业务错误码（签名过期/限流等）：返回空列表，由上层健康度统计为「零产出」而非解析异常
        logger.warning(
            "cls telegraph api returned business error: source=%s errno=%s msg=%s",
            source.name,
            errno,
            payload.get("msg"),
        )
        return []

    data = payload.get("data")
    if not isinstance(data, dict):
        logger.warning("cls telegraph payload is missing data object: source=%s", source.name)
        return []

    records = data.get("roll_data")
    if not isinstance(records, list):
        logger.warning("cls telegraph payload is missing data.roll_data array: source=%s", source.name)
        return []

    items: list[SourceItem] = []
    seen_urls: set[str] = set()
    for record in records:
        if len(items) >= source.item_limit:
            break
        if not isinstance(record, dict):
            continue

        item_id = record.get("id")
        if isinstance(item_id, bool) or not isinstance(item_id, (int, str)):
            continue
        item_id = str(item_id).strip()
        if not item_id:
            continue

        brief = record.get("brief")
        body = record.get("content")
        content_text = _clean_text(brief if isinstance(brief, str) else None) or _clean_text(
            body if isinstance(body, str) else None
        )

        title_value = record.get("title")
        raw_title = title_value.strip() if isinstance(title_value, str) else ""
        title = raw_title or _cls_title_from_body(content_text)
        if not title:
            # 标题与正文都为空的条目没有任何信息量，跳过而不是整批失败
            continue

        # `https://www.cls.cn/detail/{id}` 比 shareurl（带一次性查询参数）更干净、更稳定去重
        canonical_url = _canonicalize_url(f"/detail/{item_id}", "https://www.cls.cn/")
        if canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)

        published_at = _epoch_to_utc(record.get("ctime")) or _epoch_to_utc(record.get("modified_time"))

        # `stock_list` 是财联社给出的关联个股列表。非空即表示编辑侧已经把这条快讯
        # 挂到了具体标的上，这是比关键词表可靠得多的相关性证据，透传给入库闸门。
        # 字段缺失/类型畸形一律按"无关联个股"处理，不影响该条其余字段的解析。
        stock_list = record.get("stock_list")
        has_stock_refs = isinstance(stock_list, list) and len(stock_list) > 0

        items.append(
            SourceItem(
                title=title[:200],
                canonical_url=canonical_url,
                summary=content_text[:280] if content_text else None,
                content_text=content_text,
                content_html=None,
                published_at=published_at,
                has_stock_refs=has_stock_refs,
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
