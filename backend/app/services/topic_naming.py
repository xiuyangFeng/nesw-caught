"""主题中文别名与可读显示名。"""

from __future__ import annotations

import re

TOPIC_ALIAS_ZH: dict[str, str] = {
    "ai": "人工智能",
    "artificial": "人工智能",
    "intelligence": "人工智能",
    "chip": "芯片",
    "chips": "芯片",
    "semiconductor": "半导体",
    "semiconductors": "半导体",
    "earnings": "财报",
    "revenue": "营收",
    "guidance": "指引",
    "regulation": "监管",
    "regulatory": "监管",
    "policy": "政策",
    "tariff": "关税",
    "merger": "并购",
    "acquisition": "收购",
    "ipo": "上市",
    "fed": "美联储",
    "rate": "利率",
    "rates": "利率",
    "inflation": "通胀",
    "oil": "原油",
    "energy": "能源",
    "cloud": "云计算",
    "supply": "供应",
    "demand": "需求",
    "shipment": "出货",
    "shipments": "出货",
    "orders": "订单",
    "nvidia": "英伟达",
    "apple": "苹果",
    "tesla": "特斯拉",
    "tencent": "腾讯",
    "alibaba": "阿里巴巴",
}

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def topic_alias_zh(token: str) -> str | None:
    normalized = token.strip().lower()
    if not normalized:
        return None
    if normalized in TOPIC_ALIAS_ZH:
        return TOPIC_ALIAS_ZH[normalized]
    # 允许 "semiconductors" 一类已在表中；未知英文无别名
    return None


def resolve_topic_display_name(
    *,
    topic_key: str,
    topic_title: str,
    keywords: list[str] | None = None,
) -> str:
    """生成可读显示名：已含中文则保留；否则用关键词中文别名拼装。"""
    title = (topic_title or "").strip()
    if title and _CJK_RE.search(title):
        return title

    parts: list[str] = []
    seen: set[str] = set()
    for raw in list(keywords or []) + topic_key.replace("-", " ").split():
        token = raw.strip()
        if not token:
            continue
        alias = topic_alias_zh(token) or (token if _CJK_RE.search(token) else None)
        if alias is None or alias in seen:
            continue
        parts.append(alias)
        seen.add(alias)
        if len(parts) >= 3:
            break

    if parts:
        return "".join(parts) if all(_CJK_RE.search(p) for p in parts) else " ".join(parts)
    return title or topic_key or "市场动态"


def topic_naming_fields(
    *,
    topic_key: str | None,
    topic_title: str,
    keywords: list[str] | None = None,
) -> tuple[str, str | None]:
    """返回 (display_name, alias_zh)。alias_zh 取首个可映射英文关键词别名。"""
    kw = keywords or []
    display = resolve_topic_display_name(
        topic_key=topic_key or "",
        topic_title=topic_title,
        keywords=kw,
    )
    alias: str | None = None
    for token in kw:
        alias = topic_alias_zh(token)
        if alias:
            break
    if alias is None and topic_key:
        for token in topic_key.replace("-", " ").split():
            alias = topic_alias_zh(token)
            if alias:
                break
    return display, alias
