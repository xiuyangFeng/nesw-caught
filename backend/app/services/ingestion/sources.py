from __future__ import annotations

import json
import math
import os

from app.core.config import get_settings
from app.models.news_item import NewsItem
from app.services.ingestion.types import (
    SOURCE_TIER_RANKS,
    VALID_SOURCE_TIERS,
    VALID_SOURCE_TYPES,
    SourceDefinition,
)

# 进程内注册表缓存:path -> ((mtime_ns, size) | None, sources)。
# news_sources_file 签名未变时直接返回缓存,避免 persister 每个重复 item、
# scheduler 每个 tick 都 open + json.load + 校验。SourceDefinition 是 frozen
# dataclass 可安全共享;返回时拷贝列表本身,防调用方原地修改污染缓存。
_sources_file_cache: dict[str, tuple[tuple[int, int] | None, list[SourceDefinition]]] = {}


def clear_sources_cache() -> None:
    """清空 load_sources 的进程内缓存(测试钩子 / 配置文件热更新后调用)。"""
    _sources_file_cache.clear()


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


def _coerce_positive_int(value: object, field_name: str, source_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number for source {source_name}")
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be a finite number for source {source_name}")
    if int(value) != value or int(value) <= 0:
        raise ValueError(f"{field_name} must be positive for source {source_name}")
    return int(value)


def _normalize_markets(raw: dict[str, object]) -> list[str]:
    markets_value = raw.get("markets")
    if markets_value is None:
        market = raw.get("market")
        if market is None:
            raise ValueError("source definition is missing market")
        if not isinstance(market, str) or not market.strip():
            raise ValueError("market must be a string")
        return [market]

    if isinstance(markets_value, str) or not isinstance(markets_value, list):
        raise ValueError("markets must be an array of strings")

    markets: list[str] = []
    for market in markets_value:
        if not isinstance(market, str) or not market.strip():
            raise ValueError("markets must be an array of strings")
        markets.append(market)

    if not markets:
        raise ValueError("markets must be an array of strings")
    return markets


def _hydrate_source_definition(raw: dict[str, object]) -> dict[str, object]:
    markets = _normalize_markets(raw)
    market = raw.get("market")
    if market is not None and (not isinstance(market, str) or not market.strip()):
        raise ValueError("market must be a string")

    market = market or markets[0]

    hydrated = {
        **raw,
        "market": market,
        "tier": raw.get("tier", "primary"),
        "priority": _coerce_positive_int(raw.get("priority", 100), "priority", str(raw.get("name", "unknown"))),
        "cadence_seconds": _coerce_positive_int(
            raw.get("cadence_seconds", 300), "cadence_seconds", str(raw.get("name", "unknown"))
        ),
        "markets": markets,
        "supports_incremental": raw.get("supports_incremental", False),
    }
    return hydrated


def _validate_source_definition(source: SourceDefinition) -> None:
    if source.source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f"invalid source_type for source {source.name}: {source.source_type}")
    if source.tier not in VALID_SOURCE_TIERS:
        raise ValueError(f"invalid tier for source {source.name}: {source.tier}")
    if source.priority <= 0:
        raise ValueError(f"priority must be positive for source {source.name}")
    if source.cadence_seconds <= 0:
        raise ValueError(f"cadence_seconds must be positive for source {source.name}")
    if source.source_type == "api" and source.parser != "the_news_api_json":
        raise ValueError(f"unsupported api parser for source {source.name}: {source.parser}")


def _source_rank(priority: int, tier: str) -> tuple[int, int]:
    return (SOURCE_TIER_RANKS.get(tier, 0), -priority)


def _should_promote_source_metadata(news_item: NewsItem, source: SourceDefinition) -> bool:
    source_by_name = {item.name: item for item in load_sources()}
    existing_source = source_by_name.get(news_item.source_name)
    existing_rank = _source_rank(existing_source.priority, existing_source.tier) if existing_source else (0, 0)
    incoming_rank = _source_rank(source.priority, source.tier)
    return incoming_rank > existing_rank


def load_sources() -> list[SourceDefinition]:
    settings = get_settings()
    if not settings.news_sources_file:
        return _default_sources()

    path = settings.news_sources_file
    try:
        stat = os.stat(path)
        signature: tuple[int, int] | None = (stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        signature = None

    cached = _sources_file_cache.get(path)
    if cached is not None and cached[0] == signature:
        return list(cached[1])

    sources = _load_sources_with_registry(path, signature)
    _sources_file_cache[path] = (signature, sources)
    return list(sources)


def _load_sources_with_registry(path: str, signature: tuple[int, int] | None) -> list[SourceDefinition]:
    sources = _default_sources()
    if signature is None:
        # 配置的文件不存在:与旧行为一致,退回默认源列表。
        return sources

    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("sources registry payload must be an object")

    extras = payload.get("sources", [])
    if extras is None:
        raise ValueError("sources must be an array")
    if not isinstance(extras, list):
        raise ValueError("sources must be an array")
    for index, raw in enumerate(extras):
        if not isinstance(raw, dict):
            raise ValueError(f"source definition at index {index} must be an object")
        source = SourceDefinition(**_hydrate_source_definition(raw))
        _validate_source_definition(source)
        sources.append(source)
    return sources
