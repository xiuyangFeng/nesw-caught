"""事件（topic）聚类的收紧规则。

背景：旧规则只要两条新闻的关键词有 ≥2 个重合就并到同一事件，且没有关键词的
新闻全部落进兜底事件 "general-market-update"。结果出现 1,894 条的兜底事件，
以及 "supermicro stock just"（886 条里只有 1 条真提到 Supermicro）这类靠
"stock / just / why / non / gaap / eps / beats" 等通用词串起来的巨型伪事件。
"""

from __future__ import annotations

from app.services.topic_matching import (
    FALLBACK_TOPIC_KEY,
    is_clusterable_topic_key,
    keywords_match_topic,
    meaningful_keywords,
)


def test_meaningful_keywords_drop_generic_finance_words_and_numbers() -> None:
    assert meaningful_keywords(["supermicro", "stock", "just", "jumped", "why", "passing"]) == ["supermicro"]
    assert meaningful_keywords(["baker", "hughes", "non", "gaap", "eps", "beats"]) == ["baker", "hughes"]
    assert meaningful_keywords(["2026", "ai", "55125"]) == ["ai"]
    assert meaningful_keywords(["半导体", "芯片"]) == ["半导体", "芯片"]


def test_stock_codes_are_meaningful_not_plain_numbers() -> None:
    # A 股 6 位代码、港股 0 打头 5 位代码是主体，不能当数字丢掉
    assert meaningful_keywords(["002384", "06951", "55125", "2026"]) == ["002384", "06951"]
    assert is_clusterable_topic_key("002384 东山精密")


def test_fallback_and_generic_led_keys_are_not_clusterable() -> None:
    assert not is_clusterable_topic_key(FALLBACK_TOPIC_KEY)
    assert not is_clusterable_topic_key("")
    assert not is_clusterable_topic_key(None)
    assert not is_clusterable_topic_key("should you forget")
    assert not is_clusterable_topic_key("2026 ai")
    assert not is_clusterable_topic_key("why wall street")
    assert is_clusterable_topic_key("supermicro stock just")
    assert is_clusterable_topic_key("半导体")
    assert is_clusterable_topic_key("apple smartphone demand")


def test_generic_overlap_no_longer_merges_unrelated_companies() -> None:
    topic = ["baker", "hughes", "non", "gaap", "eps", "beats"]
    assert not keywords_match_topic(["pfizer", "non", "gaap", "eps", "beats"], topic)
    topic = ["central", "pacific", "financial", "corp", "2026", "earnings"]
    assert not keywords_match_topic(["acme", "bank", "corp", "2026", "earnings"], topic)


def test_overlap_must_include_topic_entity_and_two_meaningful_terms() -> None:
    topic = ["apple", "smartphone", "demand", "weakens"]
    assert keywords_match_topic(["apple", "sees", "softer", "smartphone", "demand"], topic)
    # 只有通用主题词重合、没有主体 → 不并
    assert not keywords_match_topic(["samsung", "smartphone", "demand"], topic)
    # 只有 1 个有效词 → 不靠重合并（单词主题靠 topic_key 精确匹配）
    assert not keywords_match_topic(["apple"], topic)
    assert not keywords_match_topic([], topic)
