"""事件（topic）聚类的匹配规则。

旧规则：关键词 ≥2 个重合即并入同一事件；无关键词的新闻全部落进兜底事件
``general-market-update``。实测出现 1,894 条的兜底事件，以及靠 "stock / just /
why / non / gaap / eps / beats" 等通用词串起来的巨型伪事件（如
"supermicro stock just" 886 条里只有 1 条真提到 Supermicro）。

新规则：
- 兜底 key、以通用词/数字打头的 key 不聚类（新闻照常入库，只是不挂事件）；
- 关键词重合只计"有效词"（去掉通用财经词和纯数字），且必须包含事件主体
  （事件的第一个有效关键词），有效重合 ≥2 才并入。
"""

from __future__ import annotations

from collections.abc import Iterable

FALLBACK_TOPIC_KEY = "general-market-update"

# 标题模板词、财报样板词、公司后缀、星期等——单独出现不能说明是同一事件。
GENERIC_TOPIC_TERMS: frozenset[str] = frozenset(
    {
        # 疑问/引导/评论体标题
        "why", "what", "how", "should", "you", "your", "can", "will", "would", "could",
        "may", "might", "this", "these", "that", "those", "all", "just", "here", "now",
        "get", "got", "think", "forget", "buy", "sell", "hold", "key", "prediction",
        "expect", "expects", "expected", "enough", "but", "amid", "over", "about", "than",
        "more", "most", "top", "best", "big", "new", "says", "said", "report", "reports",
        "reported", "according", "set", "sets", "make", "makes", "via", "per", "its",
        # 行情动词
        "stock", "stocks", "share", "shares", "price", "prices", "trade", "trading",
        "close", "closes", "open", "opens", "index", "futures", "jump", "jumps", "jumped",
        "rise", "rises", "rose", "fall", "falls", "fell", "drop", "drops", "dropped",
        "surge", "surges", "surged", "slide", "slides", "slid", "gain", "gains", "lose",
        "loses", "climb", "climbs", "sink", "sinks", "soar", "soars", "plunge", "plunges",
        "passing", "rally", "rallies", "slump", "rangebound", "higher", "lower", "up", "down",
        # 财报样板
        "non", "gaap", "eps", "beat", "beats", "miss", "misses", "inline", "line", "bottom",
        "earnings", "revenue", "revenues", "profit", "profits", "income", "loss", "losses",
        "quarter", "quarterly", "second", "third", "fourth", "first", "results", "guidance",
        "outlook", "forecast", "conference", "call", "transcript", "declares", "dividend",
        "dividends", "short", "light",
        # 公司后缀
        "inc", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "llc",
        "holdings", "holding", "group", "global", "international", "worldwide", "general",
        "financial",
        # 媒体/时间
        "rttnews", "reuters", "bloomberg", "update", "breaking", "today", "week", "weekly",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "year", "years",
    }
)


def _is_stock_code(term: str) -> bool:
    """A 股 6 位代码、港股 0 打头 5 位代码；其余纯数字（年份、金额）视为通用词。"""
    return term.isdigit() and (len(term) == 6 or (len(term) == 5 and term.startswith("0")))


def _is_meaningful(term: str) -> bool:
    term = term.strip().lower()
    if not term or term in GENERIC_TOPIC_TERMS:
        return False
    return not term.isdigit() or _is_stock_code(term)


def meaningful_keywords(keywords: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in keywords:
        term = raw.strip().lower()
        if _is_meaningful(term) and term not in seen:
            seen.add(term)
            result.append(term)
    return result


def is_clusterable_topic_key(topic_key: str | None) -> bool:
    if not topic_key or topic_key == FALLBACK_TOPIC_KEY:
        return False
    first = topic_key.replace("-", " ").split()[0]
    return _is_meaningful(first)


def keywords_match_topic(keywords: Iterable[str], topic_keywords: Iterable[str]) -> bool:
    incoming = set(meaningful_keywords(keywords))
    existing = meaningful_keywords(topic_keywords)
    if len(incoming) < 2 or not existing:
        return False
    if existing[0] not in incoming:
        return False
    return len(incoming.intersection(existing)) >= 2
