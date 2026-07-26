"""WS-5b：相关性闸门剩余误杀的回归测试 + CLS 结构化个股信号。

来源：一次真实端到端抓取里，CLS Telegraph 抓 20 条入库 0 条。逐条复盘后确认
其中大部分（台风风球 / 救灾响应 / 埃博拉）**本就应该被拒**，但下面三类是真误杀：

1. 公司行动类中文词缺失 —— "福特公司召回超56万辆汽车" 拿到 reason=none；
2. 噪声否决压过监管机构信号 —— "国家发展改革委紧急安排1亿元…台风灾害…"
   被 chinese_noise 一票否决（根因：全称 "国家发展改革委" 不含子串 "发改委"）；
3. 地缘 → 能源/航运的窄传导缺失 —— "俄军打击乌港口设施" / "美军对伊海上封锁"
   这类"军事动作打在能源航运载体上"的快讯被整体拒掉。

本文件的**反例**同样重要：它们钉住"闸门不能被开松"这条边界，
任何一次放宽词表都必须让这些条目继续被拒。
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.ingestion.parser import _parse_cls_telegraph_json
from app.services.ingestion.sources import _default_sources
from app.services.ingestion.types import SourceItem
from app.services.news_priority import evaluate_ingest_relevance_gate

FIXTURES = Path(__file__).parent / "fixtures"

# 闸门对"官方源名"有整源绕过逻辑，这里统一用一个中性源名，
# 确保用例考的是内容判定而不是源名白名单。
_NEUTRAL_SOURCE = "CLS Telegraph"


def _gate(title: str, *, summary: str | None = None, body: str | None = None, has_stock_refs: bool = False):
    return evaluate_ingest_relevance_gate(
        title=title,
        summary=summary,
        body_excerpt=body,
        source_name=_NEUTRAL_SOURCE,
        has_stock_refs=has_stock_refs,
    )


# ---------------------------------------------------------------------------
# 必修 1：公司行动类中文词
# ---------------------------------------------------------------------------


def test_product_recall_is_market_relevant() -> None:
    """修复前：reason=none 被丢弃。召回是典型的会动股价的公司行动。"""
    decision = _gate("福特公司召回超56万辆汽车")

    assert decision.passed
    assert decision.reason == "market_signal:chinese_market_phrase"


def test_corporate_action_terms_pass_the_gate() -> None:
    """一批同类公司行动/监管动作词的横向回归。"""
    titles = [
        "某上市公司因环保问题被立案调查",
        "监管对某券商作出行政处罚决定",
        "交易所向某公司下发问询函",
        "某车企宣布北美工厂停产两周",
        "某公司公告拟收购标的资产 100% 股权",
        "某集团宣布全球裁员 5000 人",
        "某地产商美元债违约",
        "某公司中标 12 亿元订单",
        "某私募举牌某上市银行",
        "某公司公告增资全资子公司",
    ]

    for title in titles:
        assert _gate(title).passed, title


def test_diplomatic_recall_is_not_a_corporate_recall() -> None:
    """收词纪律：'召回' 的外交义（召回大使）不得被当成产品召回放行。"""
    decision = _gate("该国宣布召回驻外大使以示抗议")

    assert not decision.passed


# ---------------------------------------------------------------------------
# 必修 2：监管机构信号必须压过噪声否决
# ---------------------------------------------------------------------------


def test_regulator_funding_beats_noise_veto() -> None:
    """修复前：reason=chinese_noise。明确的监管机构 + 具体金额不应被天气词否决。"""
    decision = _gate(
        "国家发展改革委紧急安排1亿元中央预算内投资支持广东台风灾害灾后应急恢复",
        body="国家发展改革委下达中央预算内投资，用于暴雨洪涝灾后恢复重建。",
    )

    assert decision.passed
    assert decision.reason == "market_signal:chinese_market_phrase"


def test_regulator_full_name_and_abbreviation_both_match() -> None:
    """全称与简称必须等价命中：'国家发展改革委' 并不包含子串 '发改委'。"""
    assert _gate("发改委召开新闻发布会介绍经济运行情况").passed
    assert _gate("国家发展改革委召开新闻发布会").passed


def test_noise_veto_still_applies_without_any_strong_signal() -> None:
    """反例：纯天气/灾害稿没有任何强信号时，噪声否决必须继续生效。"""
    decision = _gate("上海发布中心城区高温黄色预警", body="预计明日气温将超过 38 摄氏度。")

    assert not decision.passed
    assert decision.reason == "no_market_signal:chinese_noise"


# ---------------------------------------------------------------------------
# 必修 3：地缘 → 能源/航运的窄规则
# ---------------------------------------------------------------------------


def test_military_action_on_shipping_infrastructure_passes() -> None:
    """修复前：reason=none。军事动作 + 航运/能源载体同时命中才放行。"""
    for title in [
        "俄军打击乌港口设施",
        "美军称对伊海上封锁已使两艘船只失去航行能力",
        "伊朗称该国商船在里海遭乌克兰袭击致1死1伤",
        "也门武装宣布对红海一艘油轮发动袭击",
        "某国海军在霍尔木兹海峡扣押一艘油轮",
    ]:
        decision = _gate(title)
        assert decision.passed, title
        assert decision.reason == "market_signal:geo_energy_shipping", title


def test_pure_war_report_without_energy_carrier_is_rejected() -> None:
    """反例：只有军事动作、没有能源/航运载体的纯战况必须继续被拒。"""
    for title in [
        "乌军空袭致俄平民死伤",
        "两国边境交火造成多人受伤",
        "以总理计划向特朗普递交伊朗情报",
    ]:
        assert not _gate(title).passed, title


def test_transport_news_without_military_action_is_rejected() -> None:
    """反例：只有载体、没有地缘动作的交通民生稿也必须继续被拒。"""
    for title in [
        "港珠澳大桥恢复通行、通关",
        "越南籍船舶南海沉没62人遇险 中方救起39人仍有23人失联",
    ]:
        assert not _gate(title).passed, title


# ---------------------------------------------------------------------------
# 反例总集：这批必须永远被拒（防止闸门被开松）
# ---------------------------------------------------------------------------


def test_disaster_and_public_health_flashes_stay_rejected() -> None:
    for title in [
        "香港天文台将改发三号风球",
        "刚果（金）埃博拉确诊病例超3000例",
        "广东省减灾委将省Ⅲ级救灾应急响应提升至Ⅱ级",
        "国家防减救灾委启动国家四级救灾应急响应",
        "我国蜂群无人机首次实现台风过境全程立体观测",
        "澳大利亚鸟类感染禽流感情况扩散至4个州",
    ]:
        assert not _gate(title).passed, title


# ---------------------------------------------------------------------------
# 选做：CLS stock_list → SourceItem.has_stock_refs → 闸门高置信放行
# ---------------------------------------------------------------------------


def test_structured_stock_refs_bypass_keyword_tables() -> None:
    """带关联个股的快讯 definitionally 与市场相关，不必再过词表。"""
    decision = _gate("某公司就一则传闻作出说明", has_stock_refs=True)

    assert decision.passed
    assert decision.reason == "structured_stock_refs"


def test_empty_stock_refs_do_not_relax_the_gate() -> None:
    """反例：stock_list 为空时闸门行为与修复前一致，不得被顺带放宽。"""
    decision = _gate("某公司就一则传闻作出说明", has_stock_refs=False)

    assert not decision.passed


def test_source_item_defaults_to_no_stock_refs() -> None:
    """向后兼容：既有构造点不传该字段时默认 False，行为不变。"""
    item = SourceItem(
        title="标题",
        canonical_url="https://example.com/1",
        summary=None,
        content_text=None,
        published_at=None,
    )

    assert item.has_stock_refs is False


def test_cls_parser_populates_has_stock_refs() -> None:
    """CLS 解析器把 stock_list 是否非空透传到 SourceItem。"""
    source = [s for s in _default_sources() if s.name == "CLS Telegraph"][0]
    payload = json.loads((FIXTURES / "cls_roll_list_sample.json").read_text(encoding="utf-8"))
    records = payload["data"]["roll_data"]
    # fixture 本身不带 stock_list，这里就地补两种形态：非空列表 / 空列表
    records[0]["stock_list"] = [{"StockID": "sh600519", "name": "贵州茅台"}]
    records[1]["stock_list"] = []

    items = _parse_cls_telegraph_json(json.dumps(payload, ensure_ascii=False), source)

    assert items[0].has_stock_refs is True
    assert items[1].has_stock_refs is False


def test_cls_parser_tolerates_malformed_stock_list() -> None:
    """stock_list 类型畸形时降级为 False，不影响该条其余字段的解析。"""
    source = [s for s in _default_sources() if s.name == "CLS Telegraph"][0]
    payload = json.loads((FIXTURES / "cls_roll_list_sample.json").read_text(encoding="utf-8"))
    payload["data"]["roll_data"][0]["stock_list"] = "sh600519"

    items = _parse_cls_telegraph_json(json.dumps(payload, ensure_ascii=False), source)

    assert items[0].has_stock_refs is False
    assert items[0].title == "我国蜂群无人机首次实现台风过境全程立体观测"
