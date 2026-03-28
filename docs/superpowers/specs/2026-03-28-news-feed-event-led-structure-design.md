# News Feed Event-Led Structure Design

## 背景

当前 `News Feed` 的数据链路已经具备抓取、去重、情绪、topic 和个股 mentions，但首页仍然以 `NewsItem` 平铺为主。这样的问题不是“没有新闻”，而是“结构没有把市场含义表达出来”：

- 同一件事被多个来源重复报道时，会占掉首页注意力
- 首页优先展示的是文章，而不是市场事件
- `topic` 已经存在，但更适合承接持续叙事，不适合承担首页首屏的“发生了什么”
- 用户需要自己从多条标题里手动拼出“相关股票 / 板块 / 情绪 / 影响范围”

用户希望优先优化主新闻流场景，并采用“混合优先”组织方式：首页先看高优先级事件，再看主题簇，最后保留普通新闻流。

## 目标

本轮设计目标如下：

1. 将首页首屏从“原始新闻平铺”调整为“事件主卡优先”
2. 基于现有 `topic_cluster`、`news_item`、`news_stock_mention` 派生事件视图，不引入新的抓取依赖
3. 首页在同一屏内同时表达：
   - 发生了什么
   - 影响哪些股票 / 板块
   - 当前情绪方向与重要度
4. 保留现有原始新闻流作为下层证据列表，避免这轮改动过大

## 非目标

- 本轮不新增持久化 `event_cluster` 表
- 不重写已有 `topic` 生产逻辑或 LLM 分类链路
- 不在本轮实现复杂跨 topic 事件融合
- 不改新闻详情页信息架构
- 不引入个性化推荐或机器学习排序

## 方案概览

首页数据结构拆成三层：

1. `NewsItem`
   - 原始新闻事实单元
   - 用于详情页、溯源和底层证据
2. `Derived Event Card`
   - 基于近期 `topic_cluster` 派生
   - 作为首页首屏主对象
3. `Topic Watch`
   - 继续复用 `topic_cluster`
   - 作为首页第二层，承接持续发酵的主线

实现策略采用“派生视图优先”：

- 后端新增一个事件编排服务，从近期 topic 和其对应新闻中计算事件主卡
- 前端 `NewsFeedView` 首屏消费该派生结果
- 现有 `feedItems` 仍保留，作为页面下方 `News Stream`

这样可以先验证结构方向是否正确，再决定后续是否需要把事件层持久化。

## 数据模型设计

### 1. Event Card 不是新表，而是 API View

新增派生响应结构 `NewsFeedLayoutView`，包含：

- `events`
- `topics`
- `stream`

其中 `events` 为首页主卡数组，每个事件字段建议如下：

- `event_key`
  - 稳定键，首版由 `topic_id` 派生
- `event_title`
  - 优先使用 `topic_title`
- `event_summary`
  - 优先使用 `topic_summary`，回退到主新闻摘要
- `event_type`
  - 首版用规则推断：`earnings` / `regulation` / `product` / `mna` / `macro` / `supply_chain` / `market_move` / `general`
- `market`
  - 从主新闻或 topic 对应新闻推断
- `sentiment_label`
  - 基于 topic sentiment 或主新闻 sentiment
- `importance_score`
  - 直接复用 topic importance，并在展示层排序
- `last_seen_at`
  - 取 topic `last_seen_at`
- `primary_symbol`
  - 该 topic 关联 mentions 中频次最高的 symbol
- `related_symbols`
  - 去重后的前若干 symbol
- `source_count`
  - 参与该事件的 source 去重计数
- `news_count`
  - 该事件挂载的新闻数
- `news_items`
  - 只挂首页需要的前 `N` 条新闻摘要

### 2. Topic 继续承担“叙事层”

`topics` 不做结构重写，继续使用现有 `TopicItemView`，但首页只取高 importance 的前若干项作为 “Topic Watch”。

### 3. Stream 保留原始新闻列表

`stream` 直接复用现有 `NewsItemSummary` 列表，首版仍按当前排序返回，作为事件区下面的证据层。

## 编排规则

### 1. 事件生成

首版事件生成规则：

- 只从近期高优先级 topic 派生事件
- topic 至少满足以下任一条件才进入事件候选：
  - `importance_score >= 0.55`
  - 相关新闻数 `>= 2`
  - 存在至少一个 related symbol

### 2. 事件排序

首页事件按以下顺序排序：

1. `importance_score` 高优先
2. `last_seen_at` 新优先
3. `news_count` 多优先

说明：

- 首版不做复杂重新打分，先让首页结构稳定
- 后续若需要更“交易化”，可追加官方源、监管源、财报类、突发性等加权项

### 3. event_type 推断

`event_type` 首版用标题、summary、keywords 的规则映射：

- `earnings`: earnings / revenue / guidance / results / profit
- `regulation`: sec / regulator / antitrust / tariff / approval / filing / policy
- `product`: launch / release / model / chip / product / platform
- `mna`: acquire / merger / deal / acquisition / stake / buyout
- `macro`: inflation / rate / fed / ecb / cpi / gdp / jobs
- `supply_chain`: supplier / demand / shipment / order / capacity / factory
- `market_move`: rally / selloff / surge / slump / jump / drop
- 其他回退 `general`

### 4. symbol 提取

首版不做新增 NER，直接复用 `news_stock_mention`：

- `primary_symbol` 取出现频次最高的 symbol
- `related_symbols` 取前 5 个
- 若无 mentions，则允许为空

## API 设计

新增接口：

- `GET /api/news/feed-layout`

响应：

- `events`: 首页事件主卡
- `topics`: 首页主题观察
- `stream`: 原始新闻流

查询参数首版保持最小化：

- `market`
- `limit_events`
- `limit_topics`
- `limit_stream`

现有 `GET /api/news` 保持不变，避免影响其他页面。

## 前端设计

`NewsFeedView` 调整为三段：

1. `Event Radar`
   - 首屏事件主卡
   - 每张卡片展示：事件标题、摘要、情绪、市场、event_type、related symbols、挂载新闻
2. `Topic Watch`
   - 紧凑列表展示高 importance 主题
3. `News Stream`
   - 保留原始新闻卡片列表

关键原则：

- 首页第一屏优先表达“事件”，不是“文章”
- 主题只作为第二层观察，不和事件争首屏
- 原始新闻流仍然存在，用来承接完整阅读和点击详情

## 错误处理与降级

- `feed-layout` 请求失败时，前端回退到现有 `feedItems` 单层流
- 若 `events` 为空但 `stream` 存在，页面展示 “Event Radar 暂无聚合事件”
- 若 topic / mentions 不完整，允许事件卡缺少 `primary_symbol` 或 `event_type`

## 测试策略

后端最小验证包括：

- 事件编排服务对 topic/news/mentions 的聚合结果测试
- `event_type` 规则推断测试
- `GET /api/news/feed-layout` 契约测试

前端最小验证包括：

- `NewsFeedView` 首屏优先渲染 `Event Radar`
- 事件卡正确展示 related symbols 和挂载新闻
- 接口缺失或空事件时，页面保留 `News Stream`

## 取舍说明

本轮故意不直接上持久化 `event_cluster`，原因如下：

- 当前仓库已经有 `topic_cluster` 和 `news_stock_mention`，足够支撑第一版结构化首页
- 先用派生视图验证事件层价值，更符合低风险迭代
- 若首页表现明显提升，再把事件层固化入库，届时边界也会更清楚
