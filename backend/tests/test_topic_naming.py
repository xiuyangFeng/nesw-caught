"""P1-4: 主题中文别名与可读显示名。"""

from __future__ import annotations

from app.services.topic_naming import resolve_topic_display_name, topic_alias_zh


def test_topic_alias_zh_maps_common_english_keys() -> None:
    assert topic_alias_zh("ai") == "人工智能"
    assert topic_alias_zh("semiconductors") == "半导体"
    assert topic_alias_zh("earnings") == "财报"
    assert topic_alias_zh("regulation") == "监管"


def test_resolve_topic_display_name_prefers_chinese_readable_name() -> None:
    display = resolve_topic_display_name(
        topic_key="nvidia ai earnings",
        topic_title="Nvidia Ai Earnings",
        keywords=["nvidia", "ai", "earnings"],
    )
    assert "英伟达" in display or "NVIDIA" in display.upper() or "nvidia" in display.lower()
    assert "财报" in display or "人工智能" in display


def test_resolve_topic_display_name_keeps_already_chinese_title() -> None:
    display = resolve_topic_display_name(
        topic_key="宁德时代 财报",
        topic_title="宁德时代业绩超预期",
        keywords=["宁德时代", "财报"],
    )
    assert display == "宁德时代业绩超预期"


def test_resolve_topic_display_name_falls_back_to_title() -> None:
    display = resolve_topic_display_name(
        topic_key="obscure-xyz-theme",
        topic_title="Obscure Xyz Theme",
        keywords=["obscure", "xyz"],
    )
    assert display == "Obscure Xyz Theme"
