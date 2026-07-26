"""FIX-D：收紧中文闸门误放行 + 航运状态变更规则。

本轮解决前一轮（WS-5 / WS-5b）遗留的两件事：

1. **收紧 4 条误放行**。对 `backend/data/research/*.jsonl` 全量标注样本跑评估时，
   剩余 4 条 FP 全部由两个"裸词"触发：
   - `股东` —— 命中工商变更稿正文里那句模板化的"股东信息显示，该公司由 XX 全资持股"
     （"XX公司注销"、"注册资本由 45 亿增至 65 亿"）；
   - `美股` —— 命中"8点1氪"这类科技资讯汇总稿（正文"今日热点导览"顺带提一句美股涨跌）。
   收紧手段：裸词换成组合表述 / 组合条件，外加"汇总稿只按标题判定宽泛市场代称"。

2. **新增航运状态变更规则**。上一轮的 `geo_energy_shipping` 只覆盖破坏性动作
   （封锁/袭击/扣押…），"恢复通航 / 停航 / 停止作业"这类状态变更同样直接影响
   运价与油价，现在由新的 `shipping_status_change` 窄规则覆盖。

**反例是本文件的重点**：`港珠澳大桥恢复通行、通关` 极易被"恢复通行 + 港"这种松散
匹配命中，是本轮最大的陷阱。防线设在载体侧——载体词必须是真正的航运/能源实体，
单字 `港` 绝不作为载体词。
"""

from __future__ import annotations

from app.services.news_priority import evaluate_ingest_relevance_gate

# 闸门对"官方源名"有整源绕过逻辑，这里统一用中性源名，确保用例考的是内容判定。
_NEUTRAL_SOURCE = "CLS Telegraph"


def _gate(title: str, *, summary: str | None = None, body: str | None = None):
    return evaluate_ingest_relevance_gate(
        title=title,
        summary=summary,
        body_excerpt=body,
        source_name=_NEUTRAL_SOURCE,
    )


# ---------------------------------------------------------------------------
# 1. FP 收紧：标注数据集里真实存在的三类误放行
# ---------------------------------------------------------------------------

# 取自 backend/data/research/market_relevance_candidates.annotated.jsonl 的真实样本，
# 正文原样保留了触发误放行的那句"股东信息显示…全资持股"。
_REGISTRATION_CHANGE_FALSE_POSITIVES = [
    (
        "湖北交投建设集团注册资金增至65亿元",  # historical-0212-212
        "36氪获悉，爱企查App显示，近日，湖北交投建设集团有限公司发生工商变更，"
        "注册资本由45亿元人民币增至65亿元人民币，增幅约44%。"
        "股东信息显示，该公司由湖北交通投资集团有限公司全资持股。",
    ),
    (
        "山西省融资再担保集团注册资本增至约39.9亿元",  # realtime-0280-1720
        "36氪获悉，爱企查App显示，近日，山西省融资再担保集团有限公司发生工商变更，"
        "注册资本由约37.9亿元人民币增至约39.9亿元人民币。"
        "股东信息显示，该公司由山西金融投资控股集团有限公司、国家融资担保基金有限责任公司共同持股。",
    ),
    (
        "西贝旗下呼和浩特市俊义企业管理公司注销",  # historical-0137-137
        "36氪获悉，爱企查App显示，近日，呼和浩特市俊义企业管理有限公司登记状态由存续变更为注销。"
        "注册资本500万元人民币。股东信息显示，该公司由内蒙古西贝餐饮集团有限公司全资持股。",
    ),
]


def test_business_registration_changes_no_longer_pass_the_gate() -> None:
    """收紧前：裸词 '股东' 命中 '股东信息显示'，整批工商变更稿被误放行。"""
    for title, body in _REGISTRATION_CHANGE_FALSE_POSITIVES:
        decision = _gate(title, body=body)
        assert not decision.passed, f"工商变更稿不应放行：{title}（reason={decision.reason}）"


def test_tech_digest_roundup_no_longer_passes_the_gate() -> None:
    """收紧前：裸词 '美股' 命中汇总稿正文里的 '美股三大指数集体收涨'。

    样本 historical-0134-134，人工标注为「不相关」。
    """
    decision = _gate(
        "8点1氪丨宝宝巴士推送低俗广告被罚30万；山姆客服回应给三文鱼加不可生食标签；"
        "360回应“安全龙虾”私钥泄露",
        summary="今日热点导览 美股三大指数集体收涨，36氪涨超37% 韩国首尔市内地铁全线接入微信支付",
        body="今日热点导览 美股三大指数集体收涨，36氪涨超37% 儿歌APP跳转成人广告，宝宝巴士被罚30万",
    )

    assert not decision.passed, decision.reason


def test_digest_title_with_real_signal_still_passes() -> None:
    """汇总稿并非一票否决：标题自己点名了市场信号时仍然放行。"""
    decision = _gate(
        "氪星晚报｜蜜雪集团：2025年营收335.6亿元，同比增长35.2%；汇丰任命新任亚太区主管",
        body="今日热点导览。",
    )

    assert decision.passed
    assert decision.reason == "market_signal:chinese_market_phrase"


def test_digest_body_with_concrete_signal_still_passes() -> None:
    """收窄范围只针对宽泛市场代称：汇总稿正文里的具体信号词（原油/发改委）仍算数。"""
    decision = _gate(
        "8点1氪丨13年来首次，国家对油价临时调控；影石回应被大疆起诉",
        body="国家发展改革委宣布对国内成品油与原油价格实施临时调控措施。",
    )

    assert decision.passed


# ---------------------------------------------------------------------------
# 2. 真信号不回退：收紧不能误伤 "股东 / 美股" 的真实用法
# ---------------------------------------------------------------------------


def test_real_shareholder_signals_still_pass() -> None:
    """'股东' 的真实市场用法必须继续放行。"""
    for title in [
        "某公司召开2025年年度股东大会审议利润分配方案",
        "某上市公司控股股东减持1.2%股份",
        "某公司第一大股东变更为地方国资",
        "某公司股东增持计划实施完毕",
        "某公司拟将该议案提交股东会审议",
        "某项目完成B轮融资，老股东继续超额认购",
    ]:
        decision = _gate(title)
        assert decision.passed, f"真信号被误伤：{title}（reason={decision.reason}）"
        assert decision.reason == "market_signal:chinese_market_phrase", title


def test_real_us_equity_signals_still_pass() -> None:
    """'美股' 的真实行情用法必须继续放行（组合条件命中盘口/涨跌语境词）。"""
    for title in [
        "美股三大指数收跌，纳指跌0.8%",
        "美股大型科技股盘前多数上涨，英特尔涨超1%",
        "美股收涨，标普500再创新高",
        "美股开盘走低",
        "美股大型科技股盘前普跌，特斯拉跌0.67%",
    ]:
        decision = _gate(title)
        assert decision.passed, f"真信号被误伤：{title}（reason={decision.reason}）"
        assert decision.reason == "market_signal:chinese_market_phrase", title


def test_bare_us_equity_mention_without_market_context_is_rejected() -> None:
    """反例：只在文中提一句 '美股'、没有任何盘口/涨跌语境的，不再算强信号。"""
    decision = _gate("某创业者分享他的美股投资心得与人生感悟")

    assert not decision.passed, decision.reason


# ---------------------------------------------------------------------------
# 3. 航运状态变更：新增窄规则的正例
# ---------------------------------------------------------------------------


def test_shipping_status_change_flashes_pass_with_dedicated_reason() -> None:
    """状态恢复/中断类快讯对运价与油价有信息量，须放行且归因到独立标识。"""
    for title in [
        "卡塔尔宣布将恢复海上航行",
        "苏伊士运河恢复通航",
        "霍尔木兹海峡恢复通行",
        "某港口因台风停止作业",
        "红海航线中断，多家班轮公司绕行好望角",
        "该国宣布关闭输油管道",
    ]:
        decision = _gate(title)
        assert decision.passed, f"航运状态变更被误杀：{title}（reason={decision.reason}）"
        assert decision.reason == "market_signal:shipping_status_change", (title, decision.reason)


def test_shipping_status_change_requires_both_sides() -> None:
    """只有状态词、没有航运/能源载体的，一律不放行。"""
    for title in [
        "某景区索道恢复运营",
        "地铁2号线因设备故障中断行车",
        "该市宣布关闭全部中小学一天",
    ]:
        assert not _gate(title).passed, title


# ---------------------------------------------------------------------------
# 4. 陷阱反例：陆路交通民生稿绝不能被新规则放行
# ---------------------------------------------------------------------------


def test_road_bridge_traffic_news_stays_rejected() -> None:
    """本工单最大的陷阱。

    "港珠澳大桥恢复通行" 同时具备 "恢复通行" 这个状态词和一个 "港" 字，
    只要载体词里混入单字 "港"（或 "通行" 被当成载体），就会被松散匹配命中。
    这批用例把该边界钉死：载体必须是真正的航运/能源实体。
    """
    for title, body in [
        ("港珠澳大桥恢复通行、通关", None),
        ("受台风影响，港珠澳大桥封桥", None),
        ("香港天文台将改发三号风球", "预计本港风力逐渐增强。"),
        ("深中通道因大雾临时中断通行", None),
        ("香港与内地口岸恢复通关", None),
    ]:
        decision = _gate(title, body=body)
        assert not decision.passed, f"陆路交通/民生稿被误放行：{title}（reason={decision.reason}）"


def test_maritime_accident_without_status_change_stays_rejected() -> None:
    """反例：只有载体、没有状态变更的海难救援稿也必须继续被拒。"""
    assert not _gate("越南籍船舶南海沉没62人遇险 中方救起39人仍有23人失联").passed


# ---------------------------------------------------------------------------
# 5. 前两轮关键样本的横向回归
# ---------------------------------------------------------------------------


def test_previous_round_positive_samples_still_pass() -> None:
    """WS-5 / WS-5b 已修好的真信号，本轮收紧后必须全部仍然放行。"""
    for title, body in [
        ("央行下调存款准备金率0.5个百分点", None),
        ("美联储宣布降息25个基点", None),
        ("国家统计局：11月CPI同比上涨0.2%", None),
        ("证监会发布上市公司监管新规", None),
        ("商务部对原产于美国的商品加征关税", None),
        ("OPEC+宣布减产", None),
        ("福特公司召回超56万辆汽车", None),
        (
            "国家发展改革委紧急安排1亿元中央预算内投资支持广东台风灾害灾后应急恢复",
            "国家发展改革委下达中央预算内投资，用于暴雨洪涝灾后恢复重建。",
        ),
        ("俄军打击乌港口设施", None),
        ("美军称对伊海上封锁已使两艘船只失去航行能力", None),
        ("沪指涨1.2%，两市成交额突破1.5万亿元", None),
        ("某公司发布业绩预告，预计净利润同比增长80%", None),
    ]:
        decision = _gate(title, body=body)
        assert decision.passed, f"前两轮成果回退：{title}（reason={decision.reason}）"
        assert decision.reason.startswith("market_signal:"), (title, decision.reason)


def test_previous_round_noise_samples_stay_rejected() -> None:
    """噪声样本必须全部仍被拒（防止本轮新规则把闸门开松）。"""
    for title in [
        "香港天文台将改发三号风球",
        "刚果（金）埃博拉确诊病例超3000例",
        "广东省减灾委将省Ⅲ级救灾应急响应提升至Ⅱ级",
        "国家防减救灾委启动国家四级救灾应急响应",
        "我国蜂群无人机首次实现台风过境全程立体观测",
        "澳大利亚鸟类感染禽流感情况扩散至4个州",
        "乌军空袭致俄平民死伤",
        "两国边境交火造成多人受伤",
        "该国宣布召回驻外大使以示抗议",
        "明日北京天气预报：气温骤降并伴有暴雨",
    ]:
        assert not _gate(title).passed, title
