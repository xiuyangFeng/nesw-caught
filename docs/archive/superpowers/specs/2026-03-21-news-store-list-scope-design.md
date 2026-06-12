# 新闻列表状态分槽设计

## 背景

当前 `newsStore` 只有一份全局 `items` 和 `activeQuery`。`Dashboard`、`News Feed`、`Sentiment News` 都直接读写这一份列表状态，导致任一页面加载过滤结果时，会污染其他页面读取到的新闻列表。

这已经暴露出两个问题：

- 从情绪新闻页返回 Dashboard 时，首页统计会停留在情绪过滤后的数量。
- 后续如果继续新增主题页、专题页或其他定制入口，会持续出现跨页面状态串扰。

## 目标

- 保留 `detailMap`、`analysisMap` 这类全局共享的新闻详情和分析缓存。
- 将“列表数据 + 查询条件 + 加载状态”按页面职责拆开，避免不同页面互相覆盖。
- 让 Dashboard、News Feed、Sentiment News 各自只消费自己的列表槽位。

## 非目标

- 不修改后端接口、参数结构或返回格式。
- 不调整新闻详情页和分析接口逻辑。
- 不在本轮引入分页、虚拟滚动或缓存持久化。

## 方案对比

### 方案 1：继续共享一份列表，靠各页面进入时主动重载纠偏

优点：

- 改动最小。

缺点：

- 只能治已知症状，新的专题页仍会继续串状态。
- 页面职责不清，谁都能重写全局新闻列表。

### 方案 2：在 `newsStore` 内新增按页面划分的列表槽位

优点：

- 详情缓存仍能共享，列表状态又能隔离。
- 改动集中在 store 和少数消费页面，成本可控。
- 后续扩展新的新闻入口时，可继续复用同一模式。

缺点：

- 需要同时调整 `AppShell`、`Dashboard`、`News Feed`、`Sentiment News` 的取数路径和测试。

### 方案 3：把情绪页和通用新闻页都改成页面内本地状态

优点：

- 隔离最彻底。

缺点：

- 列表加载逻辑会散落在多个页面里，复用性下降。
- 实时新增新闻、统一刷新等逻辑更难集中维护。

## 结论

采用方案 2：在 `newsStore` 内保留共享详情缓存，同时拆出多个列表槽位。

## 详细设计

### 1. Store 职责拆分

`newsStore` 保留以下共享缓存：

- `detailMap`
- `analysisMap`
- `analysisLoadingMap`
- `analysisErrorMap`

新增列表槽位：

- `dashboardItems` / `dashboardQuery` / `dashboardLoading` / `dashboardLastLoadedAt`
- `feedItems` / `feedQuery` / `feedLoading` / `feedLastLoadedAt`
- `sentimentItems` / `sentimentQuery` / `sentimentLoading` / `sentimentLastLoadedAt`

### 2. Store API 拆分

新增明确的方法边界：

- `loadDashboardNews(query)`
- `loadFeedNews(query)`
- `loadSentimentNews(query)`
- `refreshDashboardNews()`

不再让页面直接通过同一个 `loadNews()` 改写共享列表。

### 3. 页面消费关系

- `AppShell` 启动时只加载 Dashboard 需要的新闻概览列表。
- `DashboardView` 只读 `dashboardItems`，统计和“最新新闻”都基于该槽位。
- `NewsFeedView` 只读 `feedItems`，筛选器也只更新 `feedQuery`。
- `SentimentNewsView` 只读 `sentimentItems`，不会再覆盖首页或通用新闻流。

### 4. SSE 与刷新策略

`news.created` 事件仍由 `newsStore.upsertNews()` 统一处理，但处理逻辑改为按槽位判断：

- Dashboard 槽位始终更新，保持首页概览新鲜。
- Feed 槽位仅在新新闻匹配当前 `feedQuery` 时插入。
- Sentiment 槽位仅在新新闻匹配当前 `sentimentQuery` 时插入。

这样可以保留当前流式更新体验，同时避免不匹配的新闻误入过滤列表。

## 测试策略

至少覆盖：

- `newsStore` 加载情绪列表时不会覆盖 Dashboard 列表。
- `DashboardView` 改为使用 `dashboardItems`。
- `NewsFeedView` 改为使用 `feedItems`。
- `SentimentNewsView` 改为使用 `sentimentItems`。
- `AppShell` 启动时调用的是 Dashboard 列表加载方法。

## 风险与取舍

- 本轮会引入更多 store 字段，短期内状态定义会更长；但这是用结构清晰换跨页面隔离，收益明确。
- 当前仍只共享详情和分析缓存，不为各槽位分别维护详情副本，避免重复数据。
