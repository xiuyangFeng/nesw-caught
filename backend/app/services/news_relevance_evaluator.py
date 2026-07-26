from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.research import EvaluationMetrics, MarketRelevanceSample
from app.services.news_signal_classifier import NewsSignalClassifier

HIGH_CONFIDENCE_MARKET_SIGNAL_TERMS = {
    "guidance",
    "revenue",
    "earnings",
    "fund",
    "funds",
    "portfolio",
    "holdings",
    "tariff",
    "policy",
    "regulation",
    "acquisition",
    "merger",
    "outlook",
    "shares",
    "stock",
    "stocks",
    "profit",
    "forecast",
    "rates",
    "bank",
    "fed",
    "ipo",
}

LOW_CONFIDENCE_MARKET_SIGNAL_TERMS = {
    "demand",
    "supply",
    "shipment",
}

MARKET_SIGNAL_PHRASES = {
    "sec proposes",
    "sec announces enforcement",
    "fund portfolio holdings",
    "reporting of fund",
    "buyback",
    "dividend",
    "share repurchase",
}

SECTOR_TRIGGER_TERMS = {
    "guidance",
    "orders",
    "order",
    "demand",
    "supply",
    "shipments",
    "shipment",
    "outlook",
    "tariff",
    "policy",
    "regulation",
    "earnings",
    "revenue",
    "recovery",
    "export",
    "controls",
}

# —— 中文市场信号词体系 ——
#
# 背景:本模块的英文词表依赖 `re.findall(r"[a-z0-9]+", text)` 分词,纯中文标题
# 的 token 集为空,所有英文规则全部失效。因此中文必须有一套独立的、按类目
# 组织的信号词体系,而不是往一张扁平短语表里塞词。
#
# 匹配方式:中文无空格分词,统一用「子串匹配」(对小写化后的全文 text 匹配,
# CJK 不受 lower() 影响,顺带让 "A股" 这类混排词也能命中)。
#
# 收词纪律(避免子串误匹配):
#   1. 不收孤立的高频泛词(如 "指数" 会命中 "指数级增长"、"市场"/"价格" 会命中
#      任何科技稿),宁可写长一点的确定性词("采购经理指数"、"市场稳定计划");
#   2. 表现类弱词("涨停"/"跟涨"/"概念"/"板块")不进强信号表,继续留在
#      concept_mover 弱通道 —— 它们在入库闸门里属于 WEAK_INGEST_REASONS,
#      单独出现不放行;
#   3. 已知负面样本里出现过的词(如 "国务院"、"二级市场"、"价格信息")一律不收。

# 货币政策 / 利率 / 汇率
CHINESE_MONETARY_POLICY_TERMS = {
    "降准",
    "存款准备金率",
    "降息",
    "加息",
    "减息",
    "利率决议",
    "基准利率",
    "政策利率",
    "贷款市场报价利率",
    "逆回购",
    "正回购",
    "中期借贷便利",
    "常备借贷便利",
    "公开市场操作",
    "货币政策",
    "量化宽松",
    "缩表",
    "国债收益率",
    "人民币中间价",
    "中间价",
    "汇率",
    "流动性投放",
}

# 宏观数据发布
CHINESE_MACRO_DATA_TERMS = {
    "居民消费价格",
    "消费者物价",
    "生产者物价",
    "工业生产者出厂价格",
    "国内生产总值",
    "采购经理指数",
    "社会融资规模",
    "广义货币",
    "失业率",
    "非农",
    "初请失业金",
    "工业增加值",
    "固定资产投资",
    "社会消费品零售",
    "进出口",
    "贸易顺差",
    "贸易逆差",
    "通胀",
    "通缩",
    "经济数据",
    "同比上涨",
    "同比下降",
    "同比增长",
    "同比下滑",
    "环比上涨",
    "环比下降",
    "环比增长",
}

# 监管机构 / 交易所 / 央行(中文源名往往只出现在标题里,不在 source_name 上)
CHINESE_REGULATOR_TERMS = {
    "证监会",
    "银保监",
    "金融监管总局",
    "人民银行",
    "央行",
    "发改委",
    "财政部",
    "商务部",
    "工信部",
    "国资委",
    "国家统计局",
    "外汇管理局",
    # WS-5b：中文快讯里机构常写全称而非简称，"国家发展改革委" 并不包含子串 "发改委"
    # （发-展-改-革-委 ≠ 发-改-委），导致 "国家发展改革委紧急安排 1 亿元中央预算内投资"
    # 拿不到任何强信号、退到噪声表被 "台风/灾害" 一票否决。补全称词根后，
    # 监管机构信号在噪声否决之前命中，恢复正确优先级。
    "发展改革委",
    "上交所",
    "深交所",
    "北交所",
    "港交所",
    "交易所",
    "美联储",
    "欧洲央行",
    "日本央行",
    "英国央行",
    "上市公司",
    "监管新规",
    "监管机构",
    "证券法",
    # 注意：只收"国务院常务会议"这一完整表述，不收裸的"国务院"
    # ——负面样本"听取国务院官员证词"会被误命中。
    "国务院常务会议",
}

# 贸易与地缘(关税/制裁/出口管制)
CHINESE_TRADE_GEOPOLITICS_TERMS = {
    "关税",
    "加征关税",
    "反倾销",
    "反补贴",
    "出口管制",
    "实体清单",
    "制裁",
    "贸易战",
    "贸易摩擦",
    "禁运",
    "出口配额",
    "供应链",
    "外贸",
    "出口信用保险",
}

# 公司行动 / 财务
CHINESE_CORPORATE_ACTION_TERMS = {
    "业绩快报",
    "业绩预告",
    "业绩说明会",
    "净利润",
    "营业收入",
    "毛利率",
    "财报",
    "年报",
    "季报",
    "中报",
    "回购股票",
    "股份回购",
    "派息",
    "分红",
    # FIX-D：裸词 "股东" 已下线。
    # 它会命中工商变更稿里那句模板化的 "股东信息显示，该公司由 XX 全资持股"
    # （"XX公司注销"、"注册资本由 45 亿增至 65 亿" 等），这类稿件与二级市场无关，
    # 在标注集里贡献了 3/4 的误放行。改成必须出现"股东"的具体动作/身份表述，
    # 真信号（股东大会 / 控股股东减持 / 第一大股东变更）一条不丢。
    "股东大会",
    "股东会",  # 覆盖 "提交股东会审议"
    "股东减持",
    "股东增持",
    "股东变更",
    "股东权益",
    "股东回报",
    "股东名册",
    "股东提案",
    "控股股东",
    "大股东",  # 覆盖 "第一大股东变更" / "第二大股东"
    "老股东",  # 融资稿里的 "老股东继续超额认购"
    "新股东",
    "主要股东",
    "减持",
    "增持",
    "定向增发",
    "配股",
    "并购",
    "重组",
    "要约收购",
    "借壳",
    "退市",
    "停牌",
    "复牌",
    "招股",
    "上市申请",
    "商誉减值",
    "自由现金流",
    "资本开支",
    "上调指引",
    "营收指引",
    "上调资本开支",
    # —— WS-5b 补充：会直接驱动股价的公司行动/监管动作 ——
    # 实测缺口："福特公司召回超 56 万辆汽车" 此前拿到 reason=none 被丢弃。
    # 收词沿用 WS-5 纪律：只收语义唯一、在 211 条负面样本里零命中的词；
    # 会误伤的裸词一律不收（见下方"刻意不收"清单）。
    "召回",
    "停产",
    "涨价",
    "提价",
    "调价",
    "中标",
    "签订合同",
    "收购",
    "要约",
    "裁员",
    "破产",
    "违约",
    "爆雷",
    "增资",
    "增发",
    "举牌",
    "股权转让",
    "问询函",
    "立案调查",
    "行政处罚",
    "被约谈",
    "断供",
    "专利诉讼",
    "集体诉讼",
    # 刻意不收（宁可漏，不可错）：
    #   "签约"  → 会命中 "签约球员/签约艺人" 等体育娱乐稿；
    #   "清算"  → 会命中 "政治清算"，其金融义已由 "破产" 覆盖（破产清算）；
    #   "下架"  → 会命中 "剧集下架/歌曲下架" 等影视稿；
    #   "分红/配股" 已在上方，"约谈" 只收带被动语态的 "被约谈"。
}

# "召回" 的假朋友：外交语境下的 "召回大使/召回驻外人员" 与市场无关。
# 只在这些完整表述出现时抵消 "召回" 的命中，不影响 "汽车召回/产品召回"。
CHINESE_RECALL_FALSE_FRIENDS = (
    "召回大使",
    "召回驻",
    "召回其",
    "召回外交",
)

# 行业与商品
CHINESE_SECTOR_COMMODITY_TERMS = {
    "原油",
    "布伦特",
    "期货",
    "现货黄金",
    "黄金价格",
    "白银",
    "沪铜",
    "铁矿石",
    "螺纹钢",
    "碳酸锂",
    "电池级碳酸锂",
    "多晶硅",
    "光伏",
    "半导体",
    "晶圆",
    "新能源汽车",
    "储能",
    "房地产",
    "楼市",
    "煤炭",
    "天然气",
    "减产",
    "增产",
    "产能过剩",
}

# 市场表现(只收确定性表述,不收 "涨停/跟涨" 这类弱词)
CHINESE_MARKET_ACTION_TERMS = {
    "沪指",
    "深成指",
    "创业板指",
    "科创板",
    "恒生指数",
    "道琼斯",
    "纳斯达克",
    "标普500",
    "股指",
    "北向资金",
    "南向资金",
    "成交额",
    "成交量",
    "总市值",
    "龙虎榜",
    "收盘上涨",
    "收盘下跌",
    "新股上市",
    "市场稳定计划",
    # 注意："美股"/"港股"/"a股"/"大盘" 这类宽泛市场代称已移出本表，
    # 改由 BROAD_MARKET_ALIAS_TERMS 单独处理（见下）。
}

# —— FIX-D：宽泛市场代称的收紧 ——
#
# "美股/港股/A股/大盘" 是科技资讯汇总稿（"8点1氪"、各类早晚报）的高频顺带词：
# 正文"今日热点导览"里提一句美股涨跌，整篇稿子却在讲罚款/客服回应/私钥泄露。
# 两道防线：
#   1. 这几个代称只在【标题范围】内对汇总稿生效（见 NEWS_DIGEST_TITLE_MARKERS）；
#   2. 其中最泛的 "美股" 还要求同时出现盘口/涨跌语境词。
# 真正的行情快讯不受影响："美股三大指数收跌" / "美股大型科技股盘前多数上涨"
# / "美股收涨" 均仍放行。
BROAD_MARKET_ALIAS_TERMS = {
    "港股",
    "a股",
    "大盘",
}

US_EQUITY_CONTEXT_TERMS = {
    "盘前",
    "盘后",
    "开盘",
    "收盘",
    "收涨",
    "收跌",
    "涨超",
    "跌超",
    "上涨",
    "下跌",
    "普跌",
    "普涨",
    "三大指数",
    "期指",
    "熔断",
    "涨幅",
    "跌幅",
    "市值",
    "上市",
    "停牌",
}

# —— FIX-D：资讯汇总稿（digest / 早晚报）识别 ——
#
# 这类稿件的正文是"当日热点罗列"，几乎必然顺带扫到某个宽泛市场代称
# （"今日热点导览：美股三大指数集体收涨…"），但稿件本身的主题由标题决定。
# 对它们把 **宽泛市场代称** 的匹配范围收窄到标题：标题里点名了美股/港股/A股
# 才算行情稿，正文顺带提一句不算。
#
# 刻意只收窄代称、不收窄整张中文词表：汇总稿正文里出现 "净利润/制裁/原油"
# 这类具体信号时仍然算数（实测这三条汇总稿都是靠具体信号而非代称放行的）。
#
# 收词纪律：只收明确的栏目名/期刊式标题标记，不收 "日报/周报"（"央行发布XX日报"
# 这类会被误伤），也不收 "盘点"（"业绩盘点" 是真信号）。
NEWS_DIGEST_TITLE_MARKERS = (
    "点1氪",  # 8点1氪 / 12点1氪
    "氪星晚报",
    "早报",
    "晚报",
    "早知道",
    "热点导览",
    "要闻汇总",
    "新闻汇总",
    "每日精选",
)

# 聚合表:保留原常量名,供外部引用与回归对照。
CHINESE_MARKET_SIGNAL_PHRASES = (
    CHINESE_MONETARY_POLICY_TERMS
    | CHINESE_MACRO_DATA_TERMS
    | CHINESE_REGULATOR_TERMS
    | CHINESE_TRADE_GEOPOLITICS_TERMS
    | CHINESE_CORPORATE_ACTION_TERMS
    | CHINESE_SECTOR_COMMODITY_TERMS
    | CHINESE_MARKET_ACTION_TERMS
)

# 中英混排的宏观/机构缩写:走 token 精确匹配(词边界),避免 "cpi" 命中英文长词。
MACRO_ACRONYM_TERMS = {
    "cpi",
    "ppi",
    "gdp",
    "pmi",
    "lpr",
    "mlf",
    "opec",
    "fomc",
    "boj",
    "pboc",
}

# 中文噪声样板:娱乐/体育/天气/生活方式。仅在没有命中任何强市场信号时否决,
# 这样 "台风影响原油运输" 之类仍能靠强信号放行。
CHINESE_NOISE_TERMS = {
    "娱乐圈",
    "明星",
    "演唱会",
    "综艺",
    "电影票房",
    "影视剧",
    "八卦",
    "恋情",
    "结婚",
    "离婚",
    "球队",
    "球员",
    "联赛",
    "夺冠",
    "进球",
    "奥运",
    "世界杯",
    "天气预报",
    "气温",
    "降雨",
    "暴雨",
    "高温预警",
    "旅游攻略",
    "美食",
    "菜谱",
    "星座",
    "彩票",
}

CHINESE_CONCEPT_SIGNAL_TERMS = {
    "概念",
    "板块",
}

CHINESE_EQUITY_MOVE_TERMS = {
    "涨停",
    "跟涨",
}

GENERIC_TECH_TERMS = {
    "camera",
    "reviewers",
    "display",
    "battery",
    "gaming",
    "smartphone",
    "laptop",
    "hands-on",
    "benchmark",
}

SHIPPING_ROUTE_TERMS = {"shipper", "shippers", "shipping", "container", "operators"}
SHIPPING_DISRUPTION_PHRASES = {"red sea", "route", "routes", "targeting"}
TAIWAN_TENSION_TERMS = {"对台", "台湾", "台海"}
ARMS_SALE_TERMS = {"军售", "导弹", "武器"}
IRAN_TENSION_TERMS = {"伊朗"}
MILITARY_ACTION_TERMS = {"军事行动", "动武", "军事打击", "空袭", "袭击"}
WAR_POWERS_PROCESS_TERMS = {"战争权力", "议案", "参议院", "投票", "否决"}

# —— WS-5b：地缘 → 能源/航运的【窄】传导规则 ——
#
# WS-5 判定"地缘 → 商品"整体超范围，这条结论保留：不做通用的地缘放行。
# 但"军事动作打在能源/航运载体上"是一条确定性极高的窄通道
# （封锁海峡、袭击港口、扣押油轮 → 直接反映在原油/运价上），
# 必须【两类词同时命中】才放行：
#   - 只有军事动作（"乌军空袭致俄平民死伤"）→ 仍然拒绝，属于纯战况；
#   - 只有载体（"港珠澳大桥恢复通行"）→ 仍然拒绝，属于交通民生。
GEOPOLITICAL_ACTION_TERMS = {
    "封锁",
    "袭击",
    "打击",
    "扣押",
    "禁运",
    "断航",
    "关闭海峡",
    "空袭",
    "轰炸",
    "击沉",
    "布雷",
    "拦截",
    "停航",
}
ENERGY_SHIPPING_CARRIER_TERMS = {
    "港口",
    "航道",
    "海峡",
    "油轮",
    "商船",
    "货轮",
    "船只",
    "船舶",
    "集装箱船",
    "航线",
    "管道",
    "lng",
    "液化天然气",
    "原油",
    "天然气",
    "炼油厂",
    "输油",
    "油田",
    "航运",
    "海运",
    "码头",
}

# —— FIX-D：航运/能源【状态变更】的窄规则 ——
#
# 上一轮的 geo_energy_shipping 只覆盖破坏性动作（封锁/袭击/扣押…），
# 但"恢复通航 / 停航 / 停止作业"这类状态变更同样直接反映在运价与油价上：
#   - "卡塔尔宣布将恢复海上航行"
#   - "苏伊士运河恢复通航"
#   - "某港口因台风停止作业"
# 规则同样要求【状态词 + 载体词】两侧同时命中，缺一不放行。
#
# 最大的陷阱是"港珠澳大桥恢复通行、通关"——陆路交通民生稿，必须继续被拒。
# 防线在【载体侧】：载体词一律是真正的航运/能源实体（港口/航道/运河/油轮…），
# 单字 "港" 绝不作为载体词（否则 "香港"、"港珠澳" 全部误命中）。
SHIPPING_STATUS_CHANGE_TERMS = {
    # 恢复类：用裸词 "恢复" 兜住 "恢复海上航行 / 恢复通航 / 恢复通行" 等各种搭配，
    # 松的一侧由载体词收紧。
    "恢复",
    "复航",
    "重开",
    "解封",
    # 中断类
    "停航",
    "断航",
    "停运",
    "停止作业",
    "暂停作业",
    "停止装卸",
    "暂停装卸",
    "停止通行",
    "暂停通行",
    "禁止通行",
    "封港",
    "封锁",
    "关闭",
    "中断",
}

# 载体词 = 已有的能源/航运载体表 + 一批"航运状态"语境下才用得上的实体词。
# 刻意不收：单字 "港"（"香港/港珠澳/港交所" 全中）、"桥"、"通行"（陆路语义）。
SHIPPING_STATUS_CARRIER_EXTRA_TERMS = {
    "运河",
    "海上航行",
    "海上运输",
    "海上通道",
    "海上航线",
    "水道",
    "泊位",
    "锚地",
    "港区",
    "港务",
}
SHIPPING_STATUS_CARRIER_TERMS = ENERGY_SHIPPING_CARRIER_TERMS | SHIPPING_STATUS_CARRIER_EXTRA_TERMS

AI_COMPUTE_ANCHOR_TERMS = {"ai", "gpu", "nvidia", "accelerator", "accelerators"}
SEMICONDUCTOR_TERMS = {"chip", "chips", "chipmaker", "chipmakers", "semiconductor", "semiconductors", "wafer"}
CHINESE_INTERNET_TERMS = {"tencent", "alibaba", "meituan", "jd", "baidu", "pdd", "netease", "gaming", "internet"}
APPLE_SUPPLY_CHAIN_TERMS = {
    "apple",
    "iphone",
    "ipad",
    "macbook",
    "airpods",
    "display",
    "camera",
    "lens",
    "consumer",
    "electronics",
    "supplier",
    "suppliers",
}


class EvaluationGuardrailError(ValueError):
    pass


@dataclass(frozen=True)
class MarketRelevanceEvaluationResult:
    metrics: EvaluationMetrics
    false_positive_ids: list[str]
    false_negative_ids: list[str]


@dataclass(frozen=True)
class MarketRelevancePredictionDetails:
    is_market_relevant: bool
    sector_tags: tuple[str, ...]
    relevance_reason: str | None


def evaluate_market_relevance(
    samples: list[MarketRelevanceSample],
    *,
    min_recall: float = 0.0,
) -> MarketRelevanceEvaluationResult:
    tp = fp = tn = fn = 0
    false_positive_ids: list[str] = []
    false_negative_ids: list[str] = []

    for sample in samples:
        if sample.predicted_market_relevant is None:
            raise EvaluationGuardrailError(
                f"sample {sample.sample_id} is missing predicted_market_relevant"
            )
        predicted = sample.predicted_market_relevant
        expected = sample.labels.market_relevant
        if predicted and expected:
            tp += 1
        elif predicted and not expected:
            fp += 1
            false_positive_ids.append(sample.sample_id)
        elif not predicted and expected:
            fn += 1
            false_negative_ids.append(sample.sample_id)
        else:
            tn += 1

    precision = _safe_divide(tp, tp + fp)
    recall = _safe_divide(tp, tp + fn)
    noise_rejection_rate = _safe_divide(tn, tn + fp)
    if recall < min_recall:
        raise EvaluationGuardrailError(f"recall {recall:.4f} fell below guardrail {min_recall:.4f}")

    return MarketRelevanceEvaluationResult(
        metrics=EvaluationMetrics(
            precision=round(precision, 4),
            recall=round(recall, 4),
            noise_rejection_rate=round(noise_rejection_rate, 4),
        ),
        false_positive_ids=false_positive_ids,
        false_negative_ids=false_negative_ids,
    )


def predict_market_relevance(
    sample: MarketRelevanceSample,
    *,
    classifier: NewsSignalClassifier | object | None = None,
) -> bool:
    return predict_market_relevance_details(sample, classifier=classifier).is_market_relevant


def predict_market_relevance_details(
    sample: MarketRelevanceSample,
    *,
    classifier: NewsSignalClassifier | object | None = None,
) -> MarketRelevancePredictionDetails:
    raw_text = " ".join(
        part
        for part in [
            sample.content.title,
            sample.content.summary or "",
            sample.content.body_excerpt or "",
        ]
        if part
    )
    text = raw_text.lower()
    tokens = set(re.findall(r"[a-z0-9]+", text))
    classifier_tokens: set[str] = set()
    if classifier is not None:
        result = classifier.classify(
            title=sample.content.title,
            summary=sample.content.summary,
            body=sample.content.body_excerpt,
            allow_llm=False,
        )
        classifier_tokens = set(getattr(result, "keywords", []))
        classifier_tokens.update(re.findall(r"[a-z0-9]+", getattr(result, "topic_key", "")))

    combined_market_tokens = tokens.union(classifier_tokens)
    # FIX-D：汇总稿（8点1氪 / 早晚报）的正文是当日热点罗列，正文里顺带提一句"美股涨了"
    # 不代表本稿与市场相关。对这类稿件把【宽泛市场代称】的匹配范围收窄到标题；
    # 具体信号词（净利润/制裁/原油…）仍按全文匹配。
    alias_text = sample.content.title.lower() if _looks_like_news_digest(sample.content.title) else text
    sector_tags = _detect_sector_tags(raw_text, combined_market_tokens)
    if combined_market_tokens.intersection(HIGH_CONFIDENCE_MARKET_SIGNAL_TERMS):
        return MarketRelevancePredictionDetails(True, sector_tags, "market_signal_term")
    if sector_tags and combined_market_tokens.intersection(LOW_CONFIDENCE_MARKET_SIGNAL_TERMS):
        return MarketRelevancePredictionDetails(True, sector_tags, "sector_signal_term")
    if any(phrase in text for phrase in MARKET_SIGNAL_PHRASES):
        return MarketRelevancePredictionDetails(True, sector_tags, "market_signal_phrase")
    # 中文强信号:子串匹配小写化全文(CJK 不受 lower() 影响,顺带覆盖 "A股")。
    if _has_chinese_market_signal(text, alias_text=alias_text):
        return MarketRelevancePredictionDetails(True, sector_tags, "chinese_market_phrase")
    # 宏观/机构缩写走 token 词边界匹配(CPI / GDP / OPEC / FOMC ...)。
    if combined_market_tokens.intersection(MACRO_ACRONYM_TERMS):
        return MarketRelevancePredictionDetails(True, sector_tags, "macro_acronym")
    # —— 以下四条同样是"强信号"窄规则,必须排在中文噪声否决【之前】——
    # WS-5b 修正:此前它们排在 CHINESE_NOISE_TERMS 之后,等于让"暴雨/气温"这类
    # 天气词可以一票否决掉"台风封锁港口影响原油运输"级别的确定性信号。
    # 规则约定统一为:噪声否决只作用于【没有命中任何强信号】的条目。
    if combined_market_tokens.intersection(SHIPPING_ROUTE_TERMS) and any(
        phrase in text for phrase in SHIPPING_DISRUPTION_PHRASES
    ):
        return MarketRelevancePredictionDetails(True, sector_tags, "shipping_disruption")
    if _looks_like_geo_energy_shipping_disruption(text):
        return MarketRelevancePredictionDetails(True, sector_tags, "geo_energy_shipping")
    if _looks_like_shipping_status_change(text):
        return MarketRelevancePredictionDetails(True, sector_tags, "shipping_status_change")
    if any(term in raw_text for term in TAIWAN_TENSION_TERMS) and any(
        term in raw_text for term in ARMS_SALE_TERMS
    ):
        return MarketRelevancePredictionDetails(True, sector_tags, "taiwan_arms_sale")
    if _looks_like_iran_war_powers_flash(raw_text):
        return MarketRelevancePredictionDetails(True, sector_tags, "iran_war_powers")
    if sector_tags and (
        combined_market_tokens.intersection(SECTOR_TRIGGER_TERMS)
        or "export controls" in text
        or "supply chain" in text
    ):
        return MarketRelevancePredictionDetails(True, sector_tags, "sector_signal")
    # 中文噪声样板:排在所有强信号之后,只否决"确实没有市场信号"的娱乐/体育/天气稿。
    # 仍然排在 concept_mover(弱信号)之前 —— 弱信号不足以对抗噪声否决。
    if any(term in text for term in CHINESE_NOISE_TERMS):
        return MarketRelevancePredictionDetails(False, sector_tags, "chinese_noise")
    if _looks_like_chinese_concept_mover(raw_text):
        return MarketRelevancePredictionDetails(True, sector_tags, "concept_mover")
    if tokens.intersection(GENERIC_TECH_TERMS) or classifier_tokens.intersection(GENERIC_TECH_TERMS):
        return MarketRelevancePredictionDetails(False, sector_tags, "generic_tech")
    return MarketRelevancePredictionDetails(False, sector_tags, None)


def predict_market_relevance_batch(
    samples: list[MarketRelevanceSample],
    *,
    session,
) -> list[MarketRelevanceSample]:
    classifier = NewsSignalClassifier(session)
    return [
        sample.model_copy(update={"predicted_market_relevant": predict_market_relevance(sample, classifier=classifier)})
        for sample in samples
    ]


def _safe_divide(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _has_chinese_market_signal(text: str, *, alias_text: str | None = None) -> bool:
    """中文强信号命中判定（`text` 须是已 lower() 的全文）。

    绝大多数词直接子串匹配即可；只有 "召回" 需要额外区分语义（见下）。
    命中假朋友时用 `continue` 而不是 `return False`，
    以免一条外交表述连带否决掉同一段文本里的其它真实信号。

    `alias_text` 是宽泛市场代称（美股/港股/A股/大盘）的匹配范围：
    普通稿件等于全文，汇总稿只给标题（见 `_looks_like_news_digest`）。
    """
    if _has_broad_market_alias_signal(text if alias_text is None else alias_text):
        return True
    for phrase in CHINESE_MARKET_SIGNAL_PHRASES:
        if phrase not in text:
            continue
        if phrase == "召回" and not _is_product_recall(text):
            continue
        return True
    return False


def _has_broad_market_alias_signal(alias_text: str) -> bool:
    """宽泛市场代称的命中判定（`alias_text` 须已 lower()）。

    "美股" 最泛（任何科技资讯汇总稿都会顺带提一句），额外要求同时出现
    盘口/涨跌语境词；"港股/A股/大盘" 语义相对确定，保持裸词匹配。
    """
    if "美股" in alias_text and any(term in alias_text for term in US_EQUITY_CONTEXT_TERMS):
        return True
    return any(term in alias_text for term in BROAD_MARKET_ALIAS_TERMS)


def _is_product_recall(text: str) -> bool:
    """区分「产品/车辆召回」（公司行动，动股价）与「召回大使」（外交动作，不相关）。"""
    return not any(friend in text for friend in CHINESE_RECALL_FALSE_FRIENDS)


def _looks_like_geo_energy_shipping_disruption(text: str) -> bool:
    """地缘/军事动作 **同时** 命中能源或航运载体时，才判为市场相关。

    单独命中任一侧都不放行：纯战况（"空袭致平民死伤"）与纯交通民生
    （"大桥恢复通行"）都应继续被闸门拒掉。
    """
    return any(term in text for term in GEOPOLITICAL_ACTION_TERMS) and any(
        term in text for term in ENERGY_SHIPPING_CARRIER_TERMS
    )


def _looks_like_shipping_status_change(text: str) -> bool:
    """航运/能源通道的 **状态变更**（恢复/中断）判为市场相关。

    必须【状态词 + 航运能源载体词】同时命中：
      - 只有状态词（"港珠澳大桥恢复通行、通关"、"大桥封桥"）→ 不放行，属陆路交通民生；
      - 只有载体词（"越南籍船舶南海沉没"）→ 不放行，属海难救援。
    """
    return any(term in text for term in SHIPPING_STATUS_CHANGE_TERMS) and any(
        term in text for term in SHIPPING_STATUS_CARRIER_TERMS
    )


def _looks_like_news_digest(title: str) -> bool:
    """标题是否是"当日热点汇总"栏目（8点1氪 / 早晚报 / 热点导览）。"""
    return any(marker in title for marker in NEWS_DIGEST_TITLE_MARKERS)


def _looks_like_chinese_concept_mover(raw_text: str) -> bool:
    return any(term in raw_text for term in CHINESE_CONCEPT_SIGNAL_TERMS) and any(
        term in raw_text for term in CHINESE_EQUITY_MOVE_TERMS
    )


def _looks_like_iran_war_powers_flash(raw_text: str) -> bool:
    return (
        any(term in raw_text for term in IRAN_TENSION_TERMS)
        and any(term in raw_text for term in MILITARY_ACTION_TERMS)
        and any(term in raw_text for term in WAR_POWERS_PROCESS_TERMS)
    )


def _detect_sector_tags(raw_text: str, tokens: set[str]) -> tuple[str, ...]:
    text = raw_text.lower()
    tags: list[str] = []

    if (
        tokens.intersection(AI_COMPUTE_ANCHOR_TERMS)
        or "ai server" in text
        or "ai servers" in text
    ) and any(term in text for term in {"ai", "gpu", "server", "compute", "accelerator", "nvidia"}):
        tags.append("ai_compute")
    if tokens.intersection(SEMICONDUCTOR_TERMS) and any(
        term in text for term in {"chip", "chips", "semiconductor", "export controls", "wafer"}
    ):
        tags.append("semiconductors")
    if tokens.intersection(CHINESE_INTERNET_TERMS) and any(
        term in text for term in {"tencent", "alibaba", "meituan", "jd", "baidu", "internet", "gaming"}
    ):
        tags.append("chinese_internet")
    if tokens.intersection(APPLE_SUPPLY_CHAIN_TERMS) and any(
        term in text for term in {"apple", "iphone", "display", "camera", "supplier", "consumer electronics"}
    ):
        tags.append("apple_supply_chain")

    return tuple(dict.fromkeys(tags))
