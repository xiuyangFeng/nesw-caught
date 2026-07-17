"""无 LLM 时的结构化摘要：主体、事件、影响对象。"""

from __future__ import annotations

import re

from app.services.topic_naming import TOPIC_ALIAS_ZH, topic_alias_zh

EVENT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("上调业绩指引", ("guidance", "raises guidance", "lifts outlook", "上调指引", "上调业绩")),
    ("发布财报", ("earnings", "results", "财报", "业绩", "营收")),
    ("监管披露", ("filing", "8-k", "10-k", "sec", "监管", "披露", "公告")),
    ("加息/利率表态", ("fed", "rates", "interest rate", "加息", "降息", "利率")),
    ("关税/贸易政策", ("tariff", "export controls", "关税", "出口管制")),
    ("并购重组", ("acquisition", "merger", "收购", "并购")),
    ("供应扰动", ("supply", "shortage", "出货", "供应", "断供")),
    ("需求变化", ("demand", "orders", "需求", "订单")),
)

IMPACT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AI算力链", ("ai", "gpu", "accelerator", "人工智能", "算力")),
    ("半导体板块", ("chip", "semiconductor", "wafer", "芯片", "半导体")),
    ("苹果供应链", ("apple", "iphone", "supplier", "苹果", "供应链")),
    ("利率敏感资产", ("fed", "rates", "bond", "利率", "债市")),
    ("相关上市公司", ("stock", "shares", "股价", "上市")),
)

ENTITY_HINTS = (
    "nvidia",
    "apple",
    "tesla",
    "tencent",
    "alibaba",
    "fed",
    "sec",
    "英伟达",
    "苹果",
    "特斯拉",
    "腾讯",
    "阿里",
    "美联储",
)


def build_structured_takeaway(
    *,
    title: str,
    summary: str | None = None,
    keywords: list[str] | None = None,
) -> str:
    haystack = " ".join(part for part in [title, summary or "", " ".join(keywords or [])] if part)
    subject = _detect_subject(haystack, keywords or [])
    event = _detect_event(haystack)
    impact = _detect_impact(haystack, keywords or [])
    return f"{subject}：{event}，影响{impact}"


def _detect_subject(haystack: str, keywords: list[str]) -> str:
    lower = haystack.lower()
    for hint in ENTITY_HINTS:
        if hint.lower() in lower or hint in haystack:
            return topic_alias_zh(hint) or hint
    for token in keywords:
        alias = topic_alias_zh(token)
        if alias:
            return alias
        if token:
            return token
    # 取标题前若干非停用词
    tokens = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", title_from_haystack(haystack))
    for token in tokens[:4]:
        if token.lower() in {"the", "a", "an", "on", "of", "and", "for"}:
            continue
        return topic_alias_zh(token) or token
    return "相关主体"


def title_from_haystack(haystack: str) -> str:
    return haystack.split("\n", 1)[0]


def _detect_event(haystack: str) -> str:
    lower = haystack.lower()
    for label, patterns in EVENT_PATTERNS:
        if any(pattern in lower or pattern in haystack for pattern in patterns):
            return label
    return "出现市场相关进展"


def _detect_impact(haystack: str, keywords: list[str]) -> str:
    lower = haystack.lower()
    for label, patterns in IMPACT_PATTERNS:
        if any(pattern in lower or pattern in haystack for pattern in patterns):
            return label
    for token in keywords:
        alias = TOPIC_ALIAS_ZH.get(token.lower())
        if alias and alias not in {"指引", "营收"}:
            return f"{alias}相关标的"
    return "相关板块"
