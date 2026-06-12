# Event Detail API Design

## 背景

当前 `EventDetailView` 已经存在，但它的数据来源仍依赖前端内存中的 `newsStore.feedLayout.events` 快照。这个方案有两个明显风险：

1. 用户刷新页面或直接打开 `/news/events/:eventKey` 时，详情页能否恢复完全依赖前端是否还能补出同一份首页快照。
2. `event_key` 只是 `feed-layout` 派生结果中的临时键，前端没有一个独立的后端事件详情接口可以查询。

这一轮的目标不是直接引入持久化事件表，而是先新增“后端可重建事件详情”能力，消除“事件详情页依赖当前前端快照”的风险。

## 目标

- 新增独立的后端事件详情接口，让 `/news/events/:eventKey` 直接请求后端。
- 复用现有 `feed-layout` 聚合规则，按当前规则重建事件详情，而不是引入新的持久化表。
- 让 `EventDetailView` 不再依赖 `newsStore.feedLayout.events` 作为主数据源。
- 保持未来可平滑演进到持久化 `eventId` 的接口形态。

## 非目标

- 本轮不新增事件持久化表。
- 本轮不保证“任意历史时刻的事件链接永久可回放”。
- 本轮不改变首页 `feed-layout` 的现有排序和聚合规则。

## 方案概述

### 1. 新增事件详情接口

新增：

- `GET /api/news/events/{event_key}`

接口语义是“按当前 feed-layout 聚合规则重建并返回这个事件键对应的当前事件详情”，而不是“读取持久化事件实体”。

返回模型建议命名为 `NewsEventDetailView`，字段基本覆盖现有 `NewsFeedEventCardView`，但补充更清晰的详情页语义：

- `event_key`
- `event_title`
- `event_summary`
- `event_type`
- `market`
- `sentiment_label`
- `importance_score`
- `last_seen_at`
- `primary_symbol`
- `related_symbols`
- `source_count`
- `news_count`
- `news_items`

本轮不额外增加新字段，但详情接口的 `news_items` 与首页卡片语义不同：

- 首页 `feed-layout.events[].news_items` 仍可保留截断，用于紧凑列表
- 详情接口 `NewsEventDetailView.news_items` 必须返回当前事件挂载的完整新闻集合，不能沿用首页的 3 条截断结果

market 作用域明确为：

- 当前接口是全局重建，不接受 `market` 参数
- `event_key` 在全局聚合结果里解析，而不是在某个 market filter 子集里解析
- 详情页语义因此是“当前全局规则下的事件详情”，不是“当前 market filter 下的事件详情”

路由定义时必须把 `/events/{event_key}` 放在现有 `/{news_id}` 详情路由之前，避免被 `news_id` 的动态段错误吞掉。

### 2. 后端重构：拆出可复用的事件构建上下文

当前 `NewsFeedLayoutService.build()` 把以下逻辑耦合在一起：

- 查询 stream items
- 查询 topics
- 查询 topic 对应 news / related symbols
- 构建 topic views
- 构建 event cards
- 计算 stream editorial scores

为了给事件详情接口复用，建议把“topics + topic_news_map + topic_mentions_map + event_cards”的构建链条拆出来，形成一个内部可复用的方法，例如：

- `_collect_topic_context(market: str | None)`  
  返回：
  - `topic_views`
  - `topic_news_map`
  - `topic_mentions_map`
- `_build_event_cards(...)`
  继续复用现有 `build_event_cards(...)`
- `_build_event_detail(...)`
  基于同一 topic context 生成一张详情对象，返回完整 `news_items`

然后：

- `build()` 继续生成首页 `NewsFeedLayoutView`
- `get_event_detail(event_key: str)` 在同一套上下文上重建 `event_cards`，再按 `event_key` 取一张返回

### 3. event_key 语义

本轮继续使用现有 `event_key`：

- topic 事件：`topic-{topic.id}`
- 融合事件：`fused-{left}-{right}`

它仍然不是永久实体 ID，但对“当前规则下可重建的事件”已经足够。

接口语义要明确：

- 若当前规则下仍能构建出同名 `event_key`，返回 200
- 若当前规则下已经无法重建该事件，返回 404
- `fused-*` 键不做额外解析存储；直接通过“重建当前 event cards 后按完整 `event_key` 精确匹配”命中

### 4. 前端数据流调整

前端新增 `apiClient.getNewsEventDetail(eventKey: string)`。

`EventDetailView` 改为：

- 进入页面后直接请求 `/api/news/events/{eventKey}`
- 本地维护 `eventDetail`、`loading`、`error/notFound`
- 成功后渲染摘要卡和时间线
- 404 时显示“事件已不存在，或已发生聚合变化”
- 不再依赖 `newsStore.feedLayout.events`

`NewsFeedView` 只负责路由跳转，不再承担事件详情页的数据恢复职责。

由于当前主分支还没有这个页面，本轮前端同时需要新增：

- `frontend/src/views/EventDetailView.vue`
- `frontend/src/views/EventDetailView.test.ts`
- `frontend/src/router/index.ts` 中的 `event-detail` 路由

### 5. 时间线规则

事件详情页仍展示当前事件的 `news_items`，规则保持不变：

- 按展示时间倒序：
  - 优先 `published_at`
  - 次选 `fetched_at`
  - 都缺失时排最后
- tie-breaker 使用 `id` 倒序

后端事件详情接口的 `news_items` 排序契约也必须与此前端规则完全一致，避免测试和运行时结果分叉。

### 6. 错误与空态

后端：

- 找不到 `event_key` 时返回 `404 event not found`

前端：

- 请求中：`正在加载事件详情`
- 404：`事件已不存在，或已发生聚合变化`
- 其他错误：`加载事件详情失败`

### 7. 向持久化事件实体的演进预留

这轮接口路径已经把“事件详情”从“新闻详情”里独立出来。未来若引入持久化事件表，可以平滑演进为：

- 路径不变或新增 `/api/news/events/{event_id}`
- `event_key` 从“可重建键”变成“兼容字段”
- `NewsEventDetailView` 基本可复用

也就是说，这一轮先解决刷新/深链脆弱性，下一轮若需要长期稳定回放，再替换底层 ID 语义即可。

## 测试策略

后端：

- 新增 `backend/tests/test_news_event_detail_api.py` 或扩展现有 `backend/tests/test_news.py`
- 覆盖：
  - `topic-*` 事件键能命中
  - `fused-*` 事件键能命中
  - 不存在的事件键返回 404
  - 返回结果中的 `news_items`、`source_count`、`news_count` 与当前聚合规则一致

前端：

- `frontend/src/views/EventDetailView.test.ts`
  - 改为断言页面调用 `getNewsEventDetail`
  - 成功时渲染事件详情
  - 404 时显示“事件已不存在...”
  - 普通错误时显示“加载事件详情失败”
- `frontend/src/api/client.test.ts`
  - 新增 `getNewsEventDetail()` 测试

## 风险与缓解

- 风险：`fused-*` 事件键的生成依赖融合顺序，如果底层排序策略变化，旧链接可能仍失效。
  - 缓解：本轮接受这一限制，因为目标是解决“依赖前端快照”的脆弱性，而不是提供永久事件 ID。
- 风险：事件详情接口每次都要重建当前事件列表，性能略高于直接查表。
  - 缓解：当前首页本来就在请求期动态构建 `feed-layout`，这轮只是复用同一套逻辑，成本可接受。
- 风险：前端从 store 切到独立请求后，`EventDetailView` 的实现将与首页解耦，测试需要同步调整。
  - 缓解：用 API client 单测和视图测试分别锁住请求行为和 UI 状态。
