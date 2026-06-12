# Newsfeed 数据源与实时性打通设计

## 背景

当前仓库已经具备新闻抓取、入库、情绪/主题处理、`SSE` 基础设施和前端 `newsStore`，但 `newsfeed` 仍存在三类结构性缺口：

- 数据源仍是平铺抓取，缺少“主源 / 补源 / 兜底源”的供给分层，跨市场稳定性无法被系统化管理
- 后端发布的是 `news.created_batch` 等后端内部事件，前端消费的是 `news.created` 增量事件，新闻新增链路没有形成稳定闭环
- 前端只能感知“列表是否 stale”，无法解释来源是否断供、新闻是否迟到、当前实时流是否正常

用户目标不是单纯追求最快，而是优先保证美股、A 股、港股三市场的稳定供给，同时兼顾新闻进入页面的速度与内容质量。

## 目标

本轮设计目标如下：

1. 为 `newsfeed` 建立可治理的数据源分层与调度策略，提升跨市场稳定供给能力
2. 将“抓取 -> 入库 -> 增量事件 -> 前端 upsert”的实时链路打通
3. 将新闻和来源的新鲜度做成可观察、可解释的产品状态，而不是仅靠前端时间阈值猜测
4. 为后续排序、去重、watchlist/topic 联动留出清晰边界，但这些能力不进入本轮 implementation plan

## 非目标

- 本轮不引入全新的商业新闻 API 供应商接入实现
- 不把新闻系统改造成独立微服务或独立消息队列集群
- 不在本轮实现复杂个性化推荐、重排序模型或机器学习召回
- 不要求把 LLM 分析、topic 聚类、mentions 提取全部放入同步实时主链路

## 方案概览

`newsfeed` 调整为四层结构：

1. 采集层：负责按市场和优先级调度数据源，确保基础供给不断流
2. 归一化层：负责 URL、标题、时间、来源标识和最小去重
3. 供给编排层：负责决定何时高频抓取、何时补抓、何时降级
4. 分发层：负责把新增新闻和后续富化结果通过统一事件模型交给前端和其他消费者

推荐实施顺序：

1. 先做数据源分层治理
2. 再做增量事件闭环
3. 再做 freshness 与 source health 可观测
4. 排序与质量优化留作后续独立 spec

本轮 implementation plan 只覆盖一个可执行交付切片：

- 后端：source registry、编排阈值、`news.created`/`news.updated`/`GET /api/news/runtime`
- 前端：`newsStore` 最小接线与 `News Feed` 顶部状态带最小展示

以下内容不进入本轮 implementation plan：

- dashboard、sentiment、watchlist 的完整新闻展示重构
- 来源级复杂诊断面板
- 排序与质量优化

## 架构设计

### 1. 采集层：Source Registry 分层

当前 `load_sources()` 只负责把默认源和配置文件源拼接为列表，不区分职责。建议把 `SourceDefinition` 扩成可治理的 source registry 元数据。

建议增加的字段：

- `tier`
  - `primary`：主源，负责基础供给
  - `secondary`：补源，负责 coverage 和断供补位
  - `fallback`：兜底源，负责冷门票和异常场景兜底
- `priority`
  - 同 tier 内排序，决定抓取先后
- `cadence_seconds`
  - 建议抓取频率，用于 worker 编排
- `supports_incremental`
  - 是否支持按时间窗口或增量游标抓取
- `markets`
  - 支持的市场列表，允许一个源覆盖多个市场
- `quality_weight`
  - 来源权重，供排序和去重使用

最小供给策略按市场定义：

- 美股：至少一个 `primary` 主源 + 一个 `secondary` 补源
- A 股：至少一个 `primary` 主源 + 一个 `fallback` 兜底源
- 港股：至少一个 `primary` 主源 + 一个 `fallback` 兜底源

配置校验与失败策略：

- 内置默认 sources 在代码中补齐完整 registry 字段，不依赖运行时自动推断
- 外部配置文件 source 在本轮允许使用旧格式；若缺少 `tier`、`priority`、`cadence_seconds`、`markets`，则按迁移默认值补齐并输出启动告警
- 旧格式迁移默认值：
  - `tier = primary`
  - `priority = 100`
  - `cadence_seconds = 300`
  - `markets = [market]`
  - `supports_incremental = false`
  - `quality_weight = 0.5`
- `tier` 只能是 `primary` / `secondary` / `fallback`；非法枚举在启动阶段报错
- `priority` 必须为正整数；`cadence_seconds` 必须大于 `0`
- 某市场缺少最小供给组合时，应用允许启动，但该市场在 runtime 中立即标记为 `degraded`，并在 `GET /api/news/runtime` 中暴露缺口原因
- 单个 source 在运行时临时失败属于运行态降级，不属于配置错误；此类场景更新 source health，但不阻断整个应用

约束：

- `stock_news_search.py` 继续保留，但职责明确为“按 symbol 触发的补抓”，不再承担全局基础供给
- `backend/data/news_sources.example.json` 及实际配置文件要能表达上述字段，否则运行时无法落地分层治理
- `quality_weight` 本轮只作为配置预留字段，不进入当前 implementation plan；若实现阶段发现无直接消费者，可直接延后删除

### 2. 归一化层：统一 canonical news item

抓取结果进入数据库前，统一走归一化步骤：

- URL 规范化
  - 复用现有 `_canonicalize_url()`，并补充 query 参数裁剪策略，避免同一篇文章因跟踪参数重复入库
- 标题去噪
  - 移除来源后缀、重复空白、常见无意义前后缀
- 时间归一
  - 所有 `published_at` 统一转为 UTC；缺失时允许为空，但不得伪造发布时间
- 来源标识归一
  - 相同来源的别名、大小写差异归并到同一 `source_name`

最小去重分两层：

- 强去重：基于规范化 URL hash，直接判断为同一新闻
- 近似去重：标题规范化后近似相同、发布时间接近、来源不同的条目视为同题新闻候选，用于后续聚合和排序降噪

本轮只要求先落地强去重和最小近似去重标记，不要求一次做复杂聚类。

### 3. 供给编排层：News Orchestrator

新增一个编排概念，不要求一定是独立类名，但职责需要从 `refresh_all()` 中显式抽离出来。它负责：

- 按市场和 source tier 决定抓取频率
- 在主源连续失败时切到补源或兜底源
- 在 watchlist / topic / symbol 明显缺新闻时，触发按需外部补抓
- 控制补抓预算，避免所有低质量源在高频轮询中放大噪音

本轮将“明显缺新闻”收敛为可验证规则：

- watchlist symbol：最近 `6` 小时内关联新闻数小于 `2`
- topic：最近 `6` 小时内关联新闻数小于 `3`
- market feed：最近 `30` 分钟内该市场无任何 `primary` 新入库新闻

补抓预算规则：

- 每个 market 每 `30` 分钟最多触发 `1` 次 fallback 补抓
- 每个 symbol 每 `6` 小时最多触发 `1` 次 `stock_news_search`
- 同一 refresh 轮次内，单个 market 最多启用 `1` 个 `secondary` 和 `1` 个 `fallback` source

建议的调度策略：

- `primary`：高频抓取，面向页面主 feed
- `secondary`：中频抓取，只在主源供给不足或 coverage 不足时补位
- `fallback`：低频抓取或异常触发抓取，用于断供恢复和冷门补全

降级规则：

- 某市场所有 `primary` 源在连续 `2` 个调度窗口失败时，将该市场标记为 `degraded`
- 当 `secondary` 或 `fallback` 成功补位时，页面应展示“当前处于补源模式”，而不是继续假装主源正常

### 4. 分发层：内容流与系统状态流分离

当前事件层已经支持 Redis Streams 和本地总线，但新闻事件偏后端内部。建议将分发层拆成两种事件：

- 内容流：给前端和业务功能消费
- 系统状态流：给页面状态和诊断消费

内容流建议事件名：

- `news.created`
  - 单条新闻已完成最小入库，可立刻出现在 feed
- `news.updated`
  - 某条新闻的情绪、topic、summary、mentions 等补齐或更新
- `news.analysis_completed`
  - 保留现有分析完成事件，用于详情页和通知

系统状态流建议事件名：

- `news.refresh_state`
  - 某次抓取轮次完成，包含整体抓取摘要
- `source.health_changed`
  - 某来源的健康状态发生显著变化，例如从 `ok` 进入 `degraded`

事件语义与幂等规则：

- `news.created`
  - 仅在数据库首次成功插入一条 `NewsItem` 时发布一次
  - 以 `news_id` 作为幂等键；前端和订阅者收到同一 `news_id` 时必须执行 upsert，而不是追加重复项
- `news.created_batch`
  - 仅供后端内部批处理订阅者消费
  - 载荷只传 `news_ids` 列表，不作为前端实时展示输入
  - 一次 refresh 最多发布一次，包含该轮新插入的全部 `news_id`
- `news.updated`
  - 仅在已存在新闻的可展示字段发生变化时发布
  - 前端收到后只替换对应条目，不改变列表顺序

原则：

- 前端新闻列表只消费内容流，不在列表流里塞系统告警
- runtime / source health 面板消费系统状态流，不直接混入单条新闻卡片

## 实时链路设计

目标链路：

`source fetch -> normalize -> dedupe -> persist -> publish news.created -> frontend upsert -> async enrich -> publish news.updated`

### 主链路

主链路只做最小必要步骤：

1. 抓取 source
2. 解析并归一化
3. 强去重
4. 持久化 `NewsItem` 与必要 `ArticleContent`
5. 发布 `news.created`

`news.created` 载荷应直接对齐前端列表卡片需要的最小字段，避免前端收到事件后还必须重新拉整页列表才能显示。

载荷契约：

```json
{
  "id": 123,
  "title": "Example headline",
  "summary": "Short summary",
  "source_name": "Example Source",
  "market": "us",
  "published_at": "2026-03-25T02:30:00Z",
  "fetched_at": "2026-03-25T02:31:03Z",
  "sentiment_label": "neutral",
  "canonical_url": "https://example.com/article"
}
```

### 富化链路

以下能力异步执行，不阻塞主链路：

- 情绪分类
- topic 聚类
- mentions 提取
- 长文抽取或增强
- LLM 分析

富化完成后发布 `news.updated` 或现有 `news.analysis_completed`。前端收到 `news.updated` 后仅替换对应条目或补齐详情缓存，不触发全量 reload。

`news.updated` 载荷契约：

```json
{
  "id": 123,
  "title": "Example headline",
  "summary": "Updated summary",
  "source_name": "Example Source",
  "market": "us",
  "published_at": "2026-03-25T02:30:00Z",
  "fetched_at": "2026-03-25T02:31:03Z",
  "sentiment_label": "positive",
  "canonical_url": "https://example.com/article",
  "updated_fields": ["sentiment_label", "summary"]
}
```

规则：

- `news.updated` 使用与 `news.created` 相同的列表级基础字段，避免前端维护 patch 合并语义
- `updated_fields` 为辅助字段，供测试和调试使用
- 详情页增强字段继续通过详情接口加载，不把 `NewsDetail` 全量塞进 `SSE`

### 批处理兼容

现有 `news.created_batch` 仍可保留给后端内部批处理订阅者使用，但不应作为前端实时消费的唯一事件。推荐：

- 后端内部继续发布 `news.created_batch`
- 同时为每条新增新闻发布 `news.created`

这样不破坏现有批处理行为，也能补齐前端实时链路。前端禁止同时消费 `news.created_batch` 和 `news.created`，以避免双重 upsert。

后端接线点：

- `app/services/news_ingestion.py`
  - 在 `refresh_all()` / `_persist_item()` 完成首次插入后发布 `news.created`
- `app/services/news_signal_pipeline.py` 或其调用方
  - 在可展示字段完成富化后发布 `news.updated`
- `app/api/routes/stream.py`
  - 本轮需要补齐 `/api/stream/events` 的事件转发实现，使 `news.created` 与 `news.updated` 能进入现有前端 `EventSource('/api/stream/events')` 链路
- `frontend/src/components/layout/AppShell.vue`
  - 现有统一事件入口继续分发 `news.created`，并新增分发 `news.updated` 给 `newsStore.upsertNewsUpdate()`

### 事件消费者迁移矩阵

| 消费者 | 当前订阅 | 调整后订阅 | 说明 |
|--------|----------|------------|------|
| `NewsSignalPipelineService` 订阅者 | `news.created_batch` | 保持 `news.created_batch` | 继续以 batch 为输入，避免把流水线拆成单条处理 |
| 通知服务 `on_news_created` | `news.created_batch` | 仍保持 `news.created_batch` | 继续以 batch 驱动，避免和前端实时事件混用 |
| 前端 `newsStore` | 无稳定新闻增量输入 | `news.created`、`news.updated` | 只消费单条增量事件，不消费 batch |
| 分析通知 | `news.analysis_completed` | 保持 `news.analysis_completed` | 无迁移 |

迁移原则：

- 后端现有订阅者本轮不迁移到 `news.created`
- `news.created` 的唯一新增消费者是前端 `newsStore`
- `news.created_batch` 继续作为后端内部批处理输入，直到后续独立 spec 再讨论是否拆分
- 因此前端与后端的事件所有权明确分离：前端只看单条内容流，后端副作用只看 batch/analysis 事件

## Freshness 与 Source Health 设计

新闻系统至少区分三种新鲜度：

### 1. 源新鲜度

回答“这个来源最近是否正常供给”。

建议暴露字段：

- `source_name`
- `market`
- `tier`
- `last_attempt_at`
- `last_success_at`
- `last_error`
- `consecutive_failures`
- `avg_fetch_latency_ms`
- `latest_news_published_at`
- `latest_news_fetched_at`
- `status`
  - `ok`
  - `delayed`
  - `degraded`
  - `offline`

### 2. 内容新鲜度

回答“这条新闻本身是快到的还是迟到的”。

建议前端可直接使用：

- `published_at`
- `fetched_at`
- `ingest_delay_seconds`

规则：

- `published_at` 缺失时，只能展示“抓取时间”，不能假装是实时发布
- 当 `fetched_at - published_at` 超出阈值时，卡片可展示“迟到”或“补录”标记

### 3. 页面新鲜度

回答“当前页面是否还在接收新的实时事件”。

建议综合：

- 服务端最近一条 `news.created` 发布时间
- 客户端 `SSE` 连接状态
- 最近一轮 `news.refresh_state` 完成时间

前端不再只用本地 `5` 分钟 stale 规则推断，而是基于服务端 freshness 聚合状态和客户端实时流状态共同判断。

### Runtime 唯一事实来源与裁决顺序

`GET /api/news/runtime` 不引入新的汇总存储，统一由请求时聚合现有事实源得出：

- 来源级状态：以 `source_health` 表为唯一事实来源
- 市场级最近新闻时间：以 `news_item` 中对应 market 的最新入库记录为唯一事实来源
- 增量流最后事件时间：以服务端事件总线状态中的 `last_published_at` 与 `last_event_name` 为唯一事实来源

定义：

- `source_health` 粒度固定为 `source_name + market`
- 多 market source 在 runtime 聚合中拆成多条 `sources[]` 记录，每条记录只对应一个 market
- `enabled market` 指当前产品明确支持且在 source registry 中未被 `disabled` 的 market；本轮固定为 `us`、`cn`、`hk`

裁决顺序：

1. `sources[].status` 只由 `source_health` 派生，不被客户端 `SSE` 状态覆盖
2. `markets[].mode` 先看最近一个成功产出新闻的 source tier
   - 最近 `30` 分钟内存在 `primary` 成功产出，则为 `primary`
   - 否则若存在 `secondary` 成功产出，则为 `secondary`
   - 否则若存在 `fallback` 成功产出，则为 `fallback`
   - 否则为 `none`，同时 `markets[].status = offline`
3. `markets[].status` 只由 source health 和 market 最近新闻时间决定，不受客户端 `SSE` 状态影响
4. `feed_status` 为页面聚合状态，优先级如下：
   - 若任一 enabled market 为 `degraded` 或 `offline`，则 `feed_status = degraded`
   - 否则若全部 enabled market 为 `live` 且最近 `5` 分钟内收到 `news.created`，则 `feed_status = live`
   - 其余情况为 `delayed`
5. 客户端顶部状态带最终展示值由两部分合成：
   - 新闻供给状态：来自 `GET /api/news/runtime.feed_status`
   - 客户端连接状态：来自 `connectionStore.state` / `runtimeStatusStore.streamStatus`
   - 若客户端 `SSE` 为 `offline/degraded`，页面显示值覆盖为 `degraded`，但不回写服务端 `feed_status`

### 阈值表

| 名称 | 阈值 | 用途 |
|------|------|------|
| recent created | `5` 分钟 | 判断 `feed_status = live` |
| market delayed | `30` 分钟无新新闻 | 判断 market `delayed` |
| primary failure degrade | 连续 `2` 个窗口失败 | 判断 market `degraded` |
| source offline | 连续 `4` 次失败 | 判断 source `offline` |
| late news | `fetched_at - published_at > 20` 分钟 | 卡片显示“迟到” |
| supplement mode | 最近 `30` 分钟内无 `primary` 成功、但有 `secondary/fallback` 成功 | 页面显示“补源模式” |

## API 与前端状态设计

### 后端 API

建议新增或扩展一组新闻 runtime / health 响应，供 `News Feed` 页面使用。

最小能力：

- `GET /api/news`
  - 继续返回列表，保持兼容
- `POST /api/news/refresh`
  - 继续保留手动刷新入口
- `GET /api/news/runtime`
  - 新增，返回 feed runtime 概览与来源级 freshness/health 聚合

`GET /api/news/runtime` 建议返回明确 schema：

```json
{
  "feed_status": "live",
  "last_refresh_finished_at": "2026-03-25T02:40:00Z",
  "last_news_created_at": "2026-03-25T02:39:40Z",
  "last_incremental_event_at": "2026-03-25T02:39:40Z",
  "degraded_market_count": 1,
  "markets": [
    {
      "market": "us",
      "status": "live",
      "mode": "primary",
      "last_primary_success_at": "2026-03-25T02:39:30Z",
      "last_news_created_at": "2026-03-25T02:39:40Z",
      "degraded_reason": null
    }
  ],
  "sources": [
    {
      "source_name": "Example Source",
      "market": "us",
      "tier": "primary",
      "status": "ok",
      "last_attempt_at": "2026-03-25T02:39:20Z",
      "last_success_at": "2026-03-25T02:39:30Z",
      "consecutive_failures": 0,
      "avg_fetch_latency_ms": 320.0,
      "latest_news_published_at": "2026-03-25T02:35:00Z",
      "latest_news_fetched_at": "2026-03-25T02:39:30Z",
      "last_error": null
    }
  ]
}
```

字段语义：

- `feed_status`
  - 服务端只表达“新闻供给状态”，不表达单个客户端的 `SSE` 连接状态
  - `live`：全部 enabled market 为 `live`，且最近 `5` 分钟内收到 `news.created`
  - `delayed`：不存在 `degraded/offline` market，但不满足 `live`
  - `degraded`：任一 enabled market 为 `degraded/offline`
- `markets[].status`
  - `live`：最近 `15` 分钟内有主源成功且最近 `30` 分钟内有新新闻
  - `delayed`：最近 `15` 分钟内有主源成功，但最近 `30` 分钟内无新新闻
  - `degraded`：主源连续 `2` 个窗口失败，但补源或兜底源仍在供给
  - `offline`：最近 `30` 分钟内该市场无任何 source 成功
- `markets[].mode`
  - `primary`：当前由主源供给
  - `secondary`：当前由补源供给
  - `fallback`：当前由兜底源供给
  - `none`：当前没有活跃供给
- `sources[].status`
  - `ok`：最近一次抓取成功，且连续失败数为 `0`
  - `delayed`：最近一次抓取成功，但 `now - last_success_at > cadence_seconds * 2`
  - `degraded`：连续失败数达到 `2`
  - `offline`：连续失败数达到 `4`

### 前端 store

传输边界：

- `news.created` 与 `news.updated` 都通过现有 `/api/stream/events` `SSE` 通道下发
- 前端 `StreamEventMap` 需要新增 `news.updated`
- 不新增第二条新闻专用 stream，也不通过轮询传输 `news.updated`

store 所有权：

- `runtimeStatusStore`
  - 继续作为 `/api/stream/status` 与全局 stream runtime 的唯一 owner
  - 负责 `SSE` 连接状态、event bus runtime、market worker runtime
- `newsStore`
  - 负责 `/api/news` 与新增的 `/api/news/runtime`
  - 负责新闻列表、新闻 runtime 聚合状态、source health 聚合状态
- `connectionStore`
  - 继续只负责 `SSE` 连接本身和事件分发，不承担新闻 runtime 聚合查询

`newsStore` 建议新增：

- `lastIncrementalAt`
- `newsRuntimeStatus`
- `sourceHealth`
- `upsertNewsUpdate()`
  - 处理 `news.updated`

约束：

- `newsStore.upsertNews()` 继续负责把 `news.created` 同步进 dashboard/feed/sentiment 三个 scope
- `dashboardLastLoadedAt`、`feedLastLoadedAt`、`sentimentLastLoadedAt` 不再被误用为真实新闻 freshness 的唯一依据
- `upsertNewsUpdate()` 的行为固定如下：
  - 若更新后的 item 仍匹配某个 scoped query，则替换原条目；若原列表中不存在则插入
  - 若更新后的 item 不再匹配某个 scoped query，则从该 scoped 列表中移除
  - scoped query 包括 `market`、`source_name`、`sentiment_label`、`q`

### 前端页面

`NewsFeedView` 顶部建议从单个 `StaleBadge` 升级为轻量状态带，明确展示：

- 当前增量流状态：`live / delayed / degraded`
- 最近入流新闻时间
- 当前异常来源数或断供市场数

来源级健康面板按市场展示：

- 美股主源状态
- A 股主源状态
- 港股主源状态
- 是否处于补源模式

新闻卡片补充时间语义：

- 发布时间
- 抓取时间
- 迟到标记（仅当明显迟到时）

说明：

- 本轮只要求实现顶部状态带与现有列表的接线
- 来源级复杂健康面板保留在设计中，但落到后续独立 plan，不作为当前单计划的必须交付
- 状态带文案规则：
  - 当 `connectionStore.state` 为 `offline/degraded` 时，显示“实时连接异常”
  - 否则若 `newsRuntimeStatus.feed_status = degraded`，显示“新闻供给降级”
  - 否则若 `newsRuntimeStatus.feed_status = delayed`，显示“新闻更新延迟”
  - 否则显示“新闻流正常”
- “当前处于补源模式” 仅在命中阈值表中的 `supplement mode` 时展示
- “迟到”标记仅在命中阈值表中的 `late news` 时展示

## 错误处理与降级

### 后端

- 单个 source 失败不得拖垮整轮 refresh
- 单个 source 失败时要更新 source health，并允许其他 source 继续产出
- 当主源失败但补源仍有产出时，系统状态应标记为 `degraded`，而不是 `ok`
- 非法 source 配置在启动阶段直接失败；运行态不再尝试“忽略并继续”

### 前端

- 没有新闻与抓取异常必须区分呈现
- `SSE` 中断时，页面仍可显示最近一次成功抓取结果，但状态带必须降级
- 当 runtime API 不可用时，允许退回当前本地 stale 逻辑，但要明确这是降级行为

## 测试策略

### 后端测试

1. source registry
   - 可从配置文件加载 `tier / priority / cadence / markets`
   - 市场最小供给组合校验生效

2. 编排层
   - 主源失败时会切到补源或兜底源
   - `stock_news_search` 只在按需补抓条件满足时触发

3. 事件链路
   - 新增新闻会发布 `news.created`
   - 富化完成会发布 `news.updated`
   - 批处理链路继续兼容 `news.created_batch`

4. freshness / health
   - source 失败、恢复、延迟场景能正确映射到 `ok / delayed / degraded / offline`

后端最小验证应覆盖相关 `pytest`，优先从 `backend/tests/test_news.py`、`backend/tests/test_news_ingestion.py`、事件相关测试扩展。

### 前端测试

1. `newsStore`
   - `news.created` 会增量插入三个新闻 scope
   - `news.updated` 会仅更新命中条目
   - runtime 状态更新不会误触发整页 reload

2. `NewsFeedView`
   - 顶部状态带能区分 `live / delayed / degraded`
   - 来源级状态展示正确
   - `SSE` 中断与“市场暂无新新闻”文案不混淆

前端最小验证应包括相关单测和 `npm --prefix frontend run build`。

## 风险与后续

- source registry 元数据一旦引入，配置质量会直接影响运行时行为，需要对缺字段和非法组合做明确校验
- 同时发布 `news.created_batch` 和 `news.created` 会增加事件数量，但换来前端和后端消费者职责分离，收益高于成本
- freshness 如果只做前端启发式判断，后续一定会出现“页面说 stale，但其实源正常”的解释问题，因此应尽早把聚合状态上移到后端
- 排序与质量优化已明确移出本轮 plan；如果后续需要做，应另起独立 spec，避免和本轮供给/实时/观测链路耦合

## 实施顺序

建议按以下阶段进入计划：

1. 数据源分层治理
   - 升级 `SourceDefinition` 与 source 配置格式
   - 建立跨市场最小供给组合与降级规则

2. 增量事件闭环
   - 发布 `news.created` / `news.updated`
   - 前端 `newsStore` 消费并增量 upsert

3. freshness 与 source health
   - 新增 `GET /api/news/runtime`
   - `News Feed` 顶部状态带最小展示

4. 排序与质量优化
   - 作为后续独立 spec，不进入本轮 implementation plan

本设计刻意把范围收敛在“供给稳定 + 实时闭环 + freshness 可见”，不在本轮同时扩展复杂推荐、全站通知重构或独立新闻服务拆分，以保证后续实现计划仍能控制在单条执行链内。
