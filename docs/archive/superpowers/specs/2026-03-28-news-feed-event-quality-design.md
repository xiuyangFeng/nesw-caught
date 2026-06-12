# News Feed Event Quality Improvement Design

## 背景

上一轮已完成 Event Radar → Topic Watch → News Stream 三层首页结构，后端 `GET /api/news/feed-layout` 已合并到 main。但当前事件层的产出质量存在三个核心问题：

1. **中文情绪和事件类型完全失效**：`NewsSignalClassifier` 的 tokenizer 只匹配 `[a-z0-9]+`，中文文本被完全跳过。`news_feed_layout` 的 `EVENT_TYPE_PATTERNS` 也只有英文关键词。结果：36Kr、财联社、智谱、MiniMax 四个中文源的 event_type 几乎全是 `general`，sentiment 几乎全是 `neutral`。

2. **importance_score 无来源质量和时间衰减**：当前公式 `min(1.0, 0.35 + news_count * 0.15 + min(abs(sentiment_score), 0.4))` 对所有来源一视同仁，且不考虑新闻时间距离。低质聚合源连续灌水可以刷高 importance，超过 24 小时的旧事件也不会自动沉底。

3. **feed-layout N+1 查询**：`NewsFeedLayoutService.build()` 对每个 topic 单独调用 `list_news_for_topic()` 和 `list_related_symbols()`，当 topic 数量 N 时产生 2N+2 条查询，影响首页加载速度。

## 目标

本轮目标是**不改变前端、不引入新依赖**，纯后端提升事件层的数据质量：

1. 让中文新闻的 sentiment 和 event_type 判定基本可用
2. 让 importance_score 能区分高低质量来源，并随时间自然衰减
3. 消除 feed-layout 的 N+1 查询

## 非目标

- 不引入 `jieba` 等中文分词外部依赖（首版用字级和短语级硬匹配）
- 不改变前端 EventFeedCard 或 NewsFeedView 的任何结构
- 不改变 `GET /api/news/feed-layout` 的响应 schema
- 不引入 embedding 或 LLM 做语义聚类
- 不新增持久化表或新 API
- 不改变新闻采集管道（ingestion）和去重逻辑

## 改动 1：中文情绪词表

### 文件：`backend/app/services/news_signal_classifier.py`

在现有 `POSITIVE_TERMS` / `NEGATIVE_TERMS` 旁增加中文词表：

```python
POSITIVE_ZH = {
    "利好": 0.7,
    "上涨": 0.6,
    "大涨": 0.8,
    "反弹": 0.5,
    "增长": 0.6,
    "超预期": 0.7,
    "强劲": 0.6,
    "突破": 0.6,
    "新高": 0.7,
    "盈利": 0.6,
    "提振": 0.6,
    "看好": 0.5,
    "机遇": 0.5,
    "乐观": 0.5,
    "利好": 0.7,
    "回暖": 0.5,
    "走高": 0.5,
    "攀升": 0.5,
    "提升": 0.4,
    "加快": 0.4,
}

NEGATIVE_ZH = {
    "利空": -0.7,
    "下跌": -0.6,
    "大跌": -0.8,
    "暴跌": -0.9,
    "下滑": -0.5,
    "亏损": -0.7,
    "衰退": -0.7,
    "风险": -0.5,
    "警告": -0.6,
    "收紧": -0.5,
    "下滑": -0.5,
    "放缓": -0.4,
    "承压": -0.5,
    "疲软": -0.6,
    "下调": -0.5,
    "违约": -0.7,
    "制裁": -0.6,
    "处罚": -0.6,
    "暴跌": -0.9,
    "崩盘": -0.9,
}
```

### tokenizer 扩展

现有 `_tokenize` 只匹配 `[a-z0-9]+`。增加中文短语扫描，返回英文 token 和中文匹配词的并集：

```python
def _tokenize(self, text: str) -> list[str]:
    en_tokens = [t for t in re.findall(r"[a-z0-9]+", text) if t and t not in STOPWORDS]
    zh_tokens = self._zh_tokens(text)
    return en_tokens + zh_tokens

def _zh_tokens(self, text: str) -> list[str]:
    all_terms = {**POSITIVE_ZH, **NEGATIVE_ZH, **THEME_ZH}
    matched = []
    seen = set()
    # 按词长降序匹配，优先匹配长词
    for term in sorted(all_terms, key=len, reverse=True):
        if term in seen:
            continue
        if term in text:
            matched.append(term)
            seen.add(term)
    return matched
```

情绪打分逻辑保持不变（`sum(POSITIVE_TERMS.get(token, 0.0))`），中文词通过同一个 dict lookup 贡献分数。

### 新增 `THEME_ZH`

用于 topic_key 生成时识别中文主题词：

```python
THEME_ZH = {
    "财报",
    "营收",
    "业绩",
    "并购",
    "收购",
    "监管",
    "上市",
    "融资",
    "芯片",
    "半导体",
    "AI",
    "人工智能",
    "模型",
    "新能源",
    "产能",
    "供应链",
    "出货",
    "订单",
    "宏观",
    "通胀",
    "降息",
    "加息",
    "利率",
}
```

`_topic_key` 方法增加对 `THEME_ZH` 命中的处理：若 keywords 中有中文 theme 词，直接参与 topic_key 构建（不再要求必须出现在 `THEME_TERMS` 中）。

## 改动 2：中文 EVENT_TYPE_PATTERNS

### 文件：`backend/app/services/news_feed_layout.py`

在 `EVENT_TYPE_PATTERNS` 中为每个类型增加中文关键词：

```python
EVENT_TYPE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("earnings", ("earnings", "revenue", "guidance", "results", "profit",
                  "财报", "营收", "业绩", "盈利", "季度", "年报", "季报")),
    ("macro", ("inflation", "rate", "fed", "ecb", "cpi", "gdp", "jobs",
               "宏观", "通胀", "CPI", "GDP", "降息", "加息", "利率", "就业", "非农")),
    ("regulation", ("sec", "regulator", "antitrust", "tariff", "approval", "filing", "policy",
                    "监管", "反垄断", "关税", "审批", "备案", "政策", "处罚", "制裁", "合规")),
    ("product", ("launch", "release", "model", "chip", "product", "platform",
                 "发布", "新品", "上线", "芯片", "产品", "型号", "旗舰")),
    ("mna", ("acquire", "merger", "deal", "acquisition", "stake", "buyout",
             "收购", "并购", "合并", "入股", "注资", "重组", "要约")),
    ("supply_chain", ("supplier", "demand", "shipment", "shipments", "order", "orders", "capacity", "factory",
                      "供应链", "产能", "出货", "订单", "需求", "交付", "工厂", "扩产")),
    ("market_move", ("rally", "selloff", "surge", "slump", "jump", "drop",
                     "大涨", "大跌", "暴涨", "暴跌", "飙升", "跳水", "异动", "拉升", "杀跌")),
)
```

`_event_type_from_texts` 逻辑不需要改动——它已经是 `haystack.lower()` 后做 `in` 检查，中文关键词直接可用。

## 改动 3：来源质量加权

### 文件：`backend/app/services/news_ingestion.py`

在 `SourceDefinition` 中已有 `tier` 字段（`primary / secondary / fallback`）。现在在 `news_feed_layout.py` 中使用它。

### 文件：`backend/app/services/news_feed_layout.py`

新增 source tier 权重映射：

```python
SOURCE_TIER_WEIGHTS: dict[str, float] = {
    "primary": 1.2,
    "secondary": 1.0,
    "fallback": 0.7,
}

DEFAULT_SOURCE_WEIGHT = 1.0
```

在 `build_event_cards` 中，计算 `weighted_importance` 时考虑 source 构成：

- 从挂载新闻的 `source_name` 查找对应 source 的 tier
- 若 source 不在已知列表中，使用 `DEFAULT_SOURCE_WEIGHT`
- `weighted_score = sum(weight_per_source) / source_count` 作为乘数修正 `importance_score`
- 需要一种方式让 feed_layout 知道 source tier。**首版方案**：在 `news_feed_layout.py` 中 import `load_sources`，构建 source_name → tier 的查找表

在 `build_event_cards` 中增加加权：

```python
def _source_weight_map() -> dict[str, float]:
    from app.services.news_ingestion import load_sources
    return {
        source.name: SOURCE_TIER_WEIGHTS.get(source.tier, DEFAULT_SOURCE_WEIGHT)
        for source in load_sources()
    }

def build_event_cards(topics, *, topic_news_map, topic_mentions_map, max_news_items=3):
    weight_map = _source_weight_map()
    ...
    for topic in topics:
        ...
        source_weights = [weight_map.get(item.source_name, DEFAULT_SOURCE_WEIGHT) for item in news_items]
        avg_weight = sum(source_weights) / len(source_weights) if source_weights else DEFAULT_SOURCE_WEIGHT
        adjusted_importance = round(topic.importance_score * avg_weight, 4)
        event_cards.append(
            NewsFeedEventCardView(
                ...
                importance_score=adjusted_importance,
                ...
            )
        )
```

## 改动 4：时间衰减

### 文件：`backend/app/services/news_feed_layout.py`

在事件排序阶段引入指数衰减，而不是修改数据库中的 `importance_score`：

```python
import math
from datetime import datetime, timezone

DECAY_LAMBDA = 0.03  # ~23h half-life: exp(-0.03 * 23) ≈ 0.5

def _decayed_importance(score: float, last_seen_at: datetime | None) -> float:
    if last_seen_at is None:
        return score
    now = datetime.now(timezone.utc)
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
    hours = max(0, (now - last_seen_at).total_seconds()) / 3600
    return round(score * math.exp(-DECAY_LAMBDA * hours), 4)
```

排序逻辑从直接用 `importance_score` 改为用 `_decayed_importance(importance_score, last_seen_at)`：

```python
event_cards.sort(
    key=lambda card: (
        _decayed_importance(card.importance_score, card.last_seen_at),
        card.last_seen_at.timestamp() if card.last_seen_at else 0.0,
        card.news_count,
    ),
    reverse=True,
)
```

注意：schema 中返回的 `importance_score` 仍保留原始值（不暴露衰减值），衰减仅影响排序。前端按现有逻辑展示即可。

## 改动 5：N+1 查询修复

### 文件：`backend/app/repositories/topic_repository.py`

新增批量查询方法：

```python
def batch_news_for_topics(self, topic_ids: list[int]) -> dict[int, list[NewsItem]]:
    if not topic_ids:
        return {}
    stmt = (
        select(TopicNewsLink.topic_cluster_id, NewsItem)
        .join(NewsItem, NewsItem.id == TopicNewsLink.news_id)
        .where(TopicNewsLink.topic_cluster_id.in_(topic_ids))
        .order_by(TopicNewsLink.topic_cluster_id, NewsItem.published_at.desc(), NewsItem.fetched_at.desc())
    )
    result: dict[int, list[NewsItem]] = {tid: [] for tid in topic_ids}
    for topic_id, news_item in self.session.execute(stmt):
        result[topic_id].append(news_item)
    return result

def batch_related_symbols(self, topic_ids: list[int], market: str | None = None) -> dict[int, list[str]]:
    if not topic_ids:
        return {}
    stmt = (
        select(TopicNewsLink.topic_cluster_id, NewsStockMention.symbol, func.count(NewsStockMention.symbol).label("cnt"))
        .join(TopicNewsLink, TopicNewsLink.news_id == NewsStockMention.news_id)
        .join(NewsItem, NewsItem.id == NewsStockMention.news_id)
        .where(TopicNewsLink.topic_cluster_id.in_(topic_ids))
        .group_by(TopicNewsLink.topic_cluster_id, NewsStockMention.symbol)
    )
    if market:
        stmt = stmt.where(NewsItem.market == market, NewsStockMention.market == market)
    raw: dict[int, list[tuple[str, int]]] = {tid: [] for tid in topic_ids}
    for topic_id, symbol, cnt in self.session.execute(stmt):
        raw[topic_id].append((symbol, cnt))
    return {
        tid: [symbol for symbol, _ in sorted(pairs, key=lambda p: (-p[1], p[0]))]
        for tid, pairs in raw.items()
    }
```

### 文件：`backend/app/services/news_feed_layout.py`

`NewsFeedLayoutService.build()` 改为：

```python
def build(self, *, market=None, limit_events=6, limit_topics=6, limit_stream=24):
    stream_items = [...]

    topics = self.topic_repository.list_all()
    topic_ids = [t.id for t in topics]

    # 2 batch queries instead of 2N
    batch_news = self.topic_repository.batch_news_for_topics(topic_ids)
    batch_symbols = self.topic_repository.batch_related_symbols(topic_ids, market=market)

    topic_views = []
    topic_news_map = {}
    topic_mentions_map = {}

    for topic in topics:
        news_items = batch_news.get(topic.id, [])
        if market:
            news_items = [item for item in news_items if item.market == market]
        if not news_items:
            continue
        related_symbols = batch_symbols.get(topic.id, [])
        topic_views.append(...)
        topic_news_map[topic.id] = [NewsItemSummary.model_validate(item, from_attributes=True) for item in news_items]
        topic_mentions_map[topic.id] = related_symbols

    ...
```

总查询从 2N+2 降到 4 条：`list_recent` + `list_all` + `batch_news_for_topics` + `batch_related_symbols`。

## 测试策略

### 后端新增/修改测试

1. **中文情绪词表测试**（`test_news_signal_pipeline.py` 或新文件）
   - 中文正面标题 → `positive`
   - 中文负面标题 → `negative`
   - 中英混合标题 → 综合判定
   - 纯中文正文无情绪词 → `neutral`

2. **中文 event_type 推断测试**（`test_news_feed_layout.py`）
   - "财报" / "营收" → `earnings`
   - "监管" / "处罚" → `regulation`
   - "收购" / "并购" → `mna`
   - "大涨" / "暴跌" → `market_move`
   - 无关键词 → `general`

3. **来源质量加权测试**
   - primary source 的事件 importance 上调
   - fallback source 的事件 importance 下调
   - 未知 source 使用默认权重

4. **时间衰减测试**
   - 1 小时内的事件几乎不衰减
   - 24 小时的事件衰减约 50%
   - 72 小时的事件大幅衰减
   - 排序验证：高衰减旧事件排在新低分事件之后

5. **N+1 查询修复回归**
   - 多 topic 场景下 feed-layout 正确返回 events/topics/stream
   - 单 topic 和空 topic 边界情况

### 前端

本轮不改前端，仅验证 `npm --prefix frontend run build` 通过。

## 风险与取舍

1. **中文词表是硬编码**：首版不用 `jieba`，意味着只匹配预定义词，无法处理新词或分词歧义。如果后续中文新闻量增大且类型多样，需要升级为真正的分词。

2. **source tier 查找依赖 `load_sources()`**：每次 `build()` 都会调用 `load_sources()` 解析 JSON，如果未来 source 数量很大可以缓存。当前 7 个源性能无影响。

3. **时间衰减只在排序时生效**：`importance_score` 字段值不变，衰减仅影响 `feed-layout` 返回的顺序。如果后续其他地方也需要衰减后的分数，需要统一到一个中央函数。

4. **不改变已入库的旧 sentiment**：本轮改动只影响新入库的新闻。已有的中文新闻 sentiment 仍为 `neutral`。如需修正，需要提供一个一次性 reprocess 脚本，但不纳入本轮 scope。
