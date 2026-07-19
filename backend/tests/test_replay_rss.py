"""历史 RSS 样本回放测试。

覆盖 docs/stability-and-evolution.md 第 3 节"测试策略/回放测试"要求：保留一组历史
RSS 样本（港股/美股，RSS 与 Atom 两种格式），用固定样本喂给现有解析入口
(`app.services.ingestion.parser._parse_rss_or_atom`)，断言解析出的标题/链接/发布时间
（尤其是港股 HKT、美股 ET 两种时区转换到 UTC 存储后的值）符合预期。

这些测试完全离线：样本文件是手工构造的历史快照，不发起任何真实网络请求。未来数据源
改版导致解析异常时，可以先跑本文件快速定位是解析逻辑坏了还是数据源本身变了。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.services.ingestion.parser import _parse_rss_or_atom
from app.services.ingestion.types import SourceDefinition

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_replay_hk_rss_sample_converts_hkt_naive_timestamp_across_day_boundary() -> None:
    """港股 RSS 样本：显式 +0800 偏移 / 裸时间戳按 market=hk 默认落到 Asia/Shanghai / 缺失发布时间。"""
    xml = _read_fixture("hk_rss_sample.xml")
    source = SourceDefinition(
        name="HK Market Wire (Sample)",
        source_type="rss",
        url="https://example-hk-wire.test/feed",
        market="hk",
    )

    items = _parse_rss_or_atom(xml, source)

    assert len(items) == 3

    hkex_item, tencent_item, hsbc_item = items

    assert hkex_item.title == "港交所公布最新上市规则修订（示例）"
    assert hkex_item.canonical_url == "https://example-hk-wire.test/story/hkex-rule-update"
    assert hkex_item.summary == "港交所今日公布上市规则修订，示例摘要文本。"
    # 显式 +08:00 偏移：09:30 HKT -> 01:30 UTC（同一天）。
    assert hkex_item.published_at == datetime(2025, 1, 15, 1, 30, tzinfo=UTC)

    assert tencent_item.title == "腾讯控股回购公告（示例）"
    assert tencent_item.canonical_url == "https://example-hk-wire.test/story/tencent-buyback"
    # dc:date 裸时间戳，market=hk 默认落到 Asia/Shanghai(+08:00)；
    # 本地 2025-06-21 02:15 HKT 跨日转换后应为 UTC 前一日 2025-06-20 18:15。
    assert tencent_item.published_at == datetime(2025, 6, 20, 18, 15, tzinfo=UTC)

    assert hsbc_item.title == "汇丰控股中期业绩预告（示例，无发布时间）"
    # 缺失发布时间字段，published_at 应解析为 None。
    assert hsbc_item.published_at is None


def test_replay_us_rss_sample_converts_et_naive_timestamp_with_dst() -> None:
    """美股 RSS 样本：显式 -0500(EST) 偏移 / 裸时间戳按 market=us 落到 America/New_York（自动识别夏令时）。"""
    xml = _read_fixture("us_rss_sample.xml")
    source = SourceDefinition(
        name="US Market Wire (Sample)",
        source_type="rss",
        url="https://example-us-wire.test/feed",
        market="us",
    )

    items = _parse_rss_or_atom(xml, source)

    assert len(items) == 3

    fed_item, apple_item, tesla_item = items

    assert fed_item.title == "Fed minutes preview headline (sample)"
    # 显式 -05:00（EST）偏移：23:50 ET 1/15 -> 04:50 UTC 1/16（跨日）。
    assert fed_item.published_at == datetime(2025, 1, 16, 4, 50, tzinfo=UTC)

    assert apple_item.title == "Apple guidance update (sample)"
    # 裸时间戳，market=us 默认落到 America/New_York；7 月为夏令时 EDT(-04:00)，
    # ZoneInfo 按日期自动选择偏移：21:15 ET 7/10 -> 01:15 UTC 7/11（跨日）。
    assert apple_item.published_at == datetime(2025, 7, 11, 1, 15, tzinfo=UTC)

    assert tesla_item.title == "Tesla delivery rumor (sample, no pubDate)"
    assert tesla_item.published_at is None


def test_replay_us_atom_sample_handles_dst_transition_day_and_naive_winter_timestamp() -> None:
    """美股 Atom 样本：覆盖 DST 结束当天（回拨前）与冬令时裸时间戳，并验证 atom link[rel=alternate] 提取。"""
    xml = _read_fixture("us_atom_sample.xml")
    source = SourceDefinition(
        name="US Market Wire Atom (Sample)",
        source_type="rss",
        url="https://example-us-wire.test/atom",
        market="us",
    )

    items = _parse_rss_or_atom(xml, source)

    assert len(items) == 2
    bank_item, retail_item = items

    assert bank_item.title == "Regional bank earnings beat headline (sample)"
    assert bank_item.canonical_url == "https://example-us-wire.test/story/regional-bank-earnings-beat"
    # 2025-11-02 是美国 DST 结束当天；<updated> 显式 -04:00（回拨前的 EDT）：
    # 01:30 EDT -> 05:30 UTC。
    assert bank_item.published_at == datetime(2025, 11, 2, 5, 30, tzinfo=UTC)

    assert retail_item.title == "Retail holiday sales forecast (sample)"
    # <published> 裸时间戳，12 月为冬令时 EST(-05:00)：08:00 ET -> 13:00 UTC。
    assert retail_item.published_at == datetime(2025, 12, 25, 13, 0, tzinfo=UTC)
