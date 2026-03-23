# Runtime Status Store Design

## Context

当前前端已经会消费 `/api/stream/status` 返回的 `market_worker` 状态，但消费路径仍然挂在 `watchlistStore.loadWatchlist()` 上。结果是：

- `AppShell` 的全局运行状态仍依赖 watchlist 数据加载
- `watchlistStore` 同时承载业务态和运行时基础设施状态，职责变脏
- 后续若增加 runtime 轮询、worker 控制或统一错误处理，还会继续挤进 watchlist 域

本轮目标是把运行时状态抽离为独立全局 store，同时保持现有 UI 展示和手动刷新行为不变。

## Options

### Approach A: 新增独立 `runtimeStatusStore`

新增一个专门的 Pinia store，统一承接 `/api/stream/status`、`market_worker`、加载态、错误态和最近刷新时间。`AppShell` 与 `WatchlistView` 都从该 store 读取运行时状态。

优点：

- 运行时状态和 watchlist 业务状态边界清晰
- 全局壳层不再依赖 watchlist 数据加载
- 后续扩展 runtime 轮询或 worker 控制时有明确归属

缺点：

- 需要同步调整初始化逻辑与现有测试

### Approach B: 保留 `watchlistStore`，只抽一个 composable

优点：

- 表面改动更小

缺点：

- 状态生命周期仍然被业务 store 驱动
- 后续能力继续扩展时仍然容易回流到 watchlist 域

### Approach C: 把 runtime 状态并入 `connectionStore`

优点：

- store 数量最少

缺点：

- `SSE` 连接状态与后台 worker 健康状态语义不同，合并后会让 store 边界变模糊

## Recommended Design

采用 Approach A。

### Store Boundary

新增 `frontend/src/stores/runtimeStatusStore.ts`，负责：

- 拉取 `/api/stream/status`
- 暴露 `streamStatus`
- 暴露 `marketWorkerStatus`
- 暴露 `loading`、`error`、`lastLoadedAt`
- 提供 `loadRuntimeStatus()`

`watchlistStore` 只保留：

- 自选股列表与行情数据
- 详情与相关新闻
- 最近一次手动刷新结果

### Component Wiring

- `AppShell` 直接读取 `runtimeStatusStore.marketWorkerStatus`
- `WatchlistView` 直接读取 `runtimeStatusStore.marketWorkerStatus`
- `AppShell.bootstrap()` 在初始化时并行调用 `runtimeStatusStore.loadRuntimeStatus()`
- `watchlistStore.loadWatchlist()` 不再请求 `/api/stream/status`

### Manual Refresh Integration

`watchlistStore.refreshMarketQuotes()` 仍留在业务 store 中，因为它是 watchlist 页的显式运维动作；但刷新成功后，除了重新加载 watchlist 数据，还需要触发一次 `runtimeStatusStore.loadRuntimeStatus()`，保证 Watchlist 页和全局壳层同时看到最新 worker 状态。

### Testing

按 TDD 覆盖：

- `runtimeStatusStore` 能正确承接 `/api/stream/status`
- `watchlistStore` 不再耦合 runtime 状态请求
- 手动刷新成功后会联动刷新 runtime 状态
- `AppShell` 与 `WatchlistView` 改为消费独立 runtime store

## Expected Outcome

完成后，前端的“系统运行态”和“watchlist 业务态”会正式分层。全局壳层、Watchlist 页面和后续 runtime 能力都共享同一个状态来源，不再依赖 `watchlistStore.loadWatchlist()` 的副作用。
