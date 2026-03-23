# Manual Refresh Result Visibility Design

## Context

当前 Watchlist 页面已经支持“立即刷新一轮”，但用户点击后只能看到按钮 loading 和错误提示，看不到这次人工刷新是否成功、触发时间是多少、到底刷新了多少个 symbol。

## Goal

把手动刷新结果直接回填到 Watchlist 页面状态面板，形成完整的人工重试反馈闭环。

## Options

### Approach A: 仅在 `watchlistStore` 存最近一次手动刷新结果

按钮调用完成后，把接口返回的 `quotes_count`、`symbols`、`triggered_at` 缓存在 `watchlistStore`，页面原地展示。

优点：

- 最小改动
- 不新增接口和全局状态

缺点：

- 只对当前会话有效，刷新页面后会丢失

### Approach B: 持久化到后端状态源

优点：

- 可跨页面/刷新保留

缺点：

- 对当前需求过大

## Recommended Design

采用 Approach A。

### UI

在 Watchlist 页 `market-worker` 状态面板中增加一段“最近手动刷新”摘要，展示：

- 触发时间
- 刷新了多少个 symbol
- 如果有 symbol 列表，展示前几个或原样拼接

### Store Behavior

- `refreshMarketQuotes()` 成功后保存 `lastManualRefreshResult`
- 失败时不覆盖上一次成功结果，只更新错误提示

### Testing

覆盖：

- store 成功后保存 `lastManualRefreshResult`
- WatchlistView 渲染这段摘要

## Expected Outcome

完成后，用户点击“立即刷新一轮”后能立刻看到这次操作的明确结果，不需要靠猜测判断是否生效。
