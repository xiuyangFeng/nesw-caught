# Manual Market Refresh Design

## Context

当前系统已经能：

- 通过独立 `market-worker` 连续生产行情
- 在 Watchlist 和 AppShell 中显示 worker 状态

但用户仍然缺少一个“看到 worker 异常后，立即主动触发一轮刷新”的操作入口。

## Design Goal

提供一个显式的人工运维动作：

- 默认生产者仍然是独立 worker
- 用户可在 UI 上点击“立即刷新一轮”
- 后端执行一次同步刷新并发布 `market.watchlist_refreshed`
- 这不是日常生产路径，只是人工重试/诊断工具

## Options

### Approach A: 新增 `POST /api/market/refresh`

Web API 显式提供一次性刷新接口，调用 `QuoteService.refresh_watchlist_quotes()` 并发布事件。

优点：

- 最小闭环
- 前端易接入
- 不影响 worker 的常驻职责

缺点：

- 人工请求会临时在 Web 进程里执行一次上游拉取

### Approach B: 通过数据库/消息队列给 worker 发“refresh now”

优点：

- 更纯粹，所有刷新都由 worker 执行

缺点：

- 当前项目没有 worker 命令通道，改动面过大

## Recommended Design

采用 Approach A，并明确标注这是“人工触发的一次性刷新”。

### Backend

新增 `POST /api/market/refresh`：

- 用 `QuoteService.refresh_watchlist_quotes()` 拉取一轮
- 发布 `market.watchlist_refreshed`
- 返回本轮刷新摘要：
  - `quotes_count`
  - `symbols`
  - `triggered_at`

### Frontend

在 Watchlist 页面状态面板和/或壳层状态里提供一个按钮：

- 文案：`立即刷新一轮`
- 点击后调用 `apiClient.refreshMarketQuotes()`
- 成功后重新加载 watchlist + stream status
- 失败则显示错误提示

### Testing

覆盖：

- backend route 调用 refresh service 并发布事件
- watchlist store 暴露手动刷新 action
- WatchlistView 显示按钮和错误/加载态

## Expected Outcome

完成后，用户看到 worker `degraded` 时，可以直接从 UI 主动触发一轮行情刷新，而不需要切回终端或重启整个 worker。
