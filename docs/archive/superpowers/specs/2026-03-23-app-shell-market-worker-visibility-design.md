# App Shell Market Worker Visibility Design

## Context

当前 Watchlist 页面已经能显示 `market-worker` 状态，但这仍要求用户先进入 Watchlist 才能发现行情生产链路是否正常。对于整个产品来说，行情链路已经是全局基础设施，状态只出现在单页里还不够。

## Options

### Approach A: 复用 `watchlistStore`，在 `AppShell` 展示

`AppShell` 目前已经在启动时调用 `watchlistStore.loadWatchlist()`，因此可以直接读取 `watchlistStore.marketWorkerStatus` 并渲染一个轻量状态块。

优点：

- 无需新增 store 或 API 请求
- 改动最小
- 与现有壳层状态区自然融合

缺点：

- 壳层与 watchlist store 的耦合继续增加一点

### Approach B: 新增全局 runtime store

抽一个专门的 runtime/status store，统一承接 stream status 和 worker status。

优点：

- 长远更干净

缺点：

- 对当前需求过大

## Recommended Design

采用 Approach A。

### UI Placement

把 `market-worker` 状态放到 `AppShell` 的 `System Status` 区域，与 SSE 状态并列，至少展示：

- worker 状态
- 最近成功时间
- 最近错误摘要（有则显示）

### Tone

- `ok`：正向
- `degraded`：警告/负向
- `null`：未知

### Testing

更新 `AppShell` 测试，锁定：

- `market-worker` 文案会被渲染
- `degraded` 状态和错误提示可见

## Expected Outcome

完成后，任何页面下用户都能在壳层看到行情 worker 的健康度，不需要切到 Watchlist 才知道行情生产链路是否正常。
