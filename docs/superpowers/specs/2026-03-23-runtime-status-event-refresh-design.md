# Runtime Status Event Refresh Design

## Context

上一轮已经把 `/api/stream/status` 请求收口到 `runtimeStatusStore`，但 runtime 快照目前仍主要依赖：

- 应用启动
- 显式人工动作（例如手动刷新行情）

这意味着壳层中的 runtime 指标不会随着 `SSE` 事件自然变新。虽然连接状态本身会随 `SSE` 改变，但 `market_worker` 最近成功时间、最近 quotes 数、事件层 backend 状态等字段仍可能停留在旧快照。

本轮目标是在不引入固定轮询的前提下，让 runtime 状态在关键 `SSE` 事件后做一次低频、节流的自动刷新。

## Options

### Approach A: 对关键 `SSE` 事件做节流刷新

在 `runtimeStatusStore` 中增加一个“若过期则刷新”的入口，由 `AppShell` 在 `watchlist.movement` 和 `stream.keepalive` 等关键事件后调用。store 自己负责最小刷新间隔与并发保护。

优点：

- 不需要长期定时器
- 只在系统确实活跃时更新 runtime 快照
- 对现有架构侵入最小

缺点：

- 如果长时间没有相关事件，runtime 快照仍然不会自动前进

### Approach B: 固定时间轮询 `/api/stream/status`

优点：

- 语义直接

缺点：

- 无论系统是否活跃都会持续请求
- 和刚完成的请求收口目标相冲突

### Approach C: 完全依赖 `SSE` 负载本身，不再刷新 runtime 接口

优点：

- 零额外请求

缺点：

- 当前 `SSE` 事件负载并不包含完整的 `market_worker` runtime 视图
- 会把后端契约扩大成新的事件设计工作

## Recommended Design

采用 Approach A。

### Store API

在 `runtimeStatusStore` 中新增：

- `loadRuntimeStatusIfStale(maxAgeSeconds = 15)`

行为：

- 若当前正在加载，直接返回
- 若 `lastLoadedAt` 仍在有效期内，直接返回
- 否则调用现有 `loadRuntimeStatus()`

### Event Triggers

`AppShell` 在 `connectionStore.connect()` 的事件回调中：

- `watchlist.movement` 后调用 `runtimeStatusStore.loadRuntimeStatusIfStale()`
- `stream.keepalive` 后也调用 `runtimeStatusStore.loadRuntimeStatusIfStale()`

其中 `watchlist.movement` 保证自选股链路活跃时 runtime 会被更新；`stream.keepalive` 则为系统仍在线但没有业务事件时提供低频补刷入口。

### Throttling

刷新节流逻辑放在 store 内，而不是组件内，避免多个消费方未来重复发明同一套防抖/节流规则。

默认最小刷新间隔使用 15 秒，和当前 `market-worker` 轮询节奏同级，不追求逐秒实时，只保证运行态不长期陈旧。

### Testing

按 TDD 覆盖：

- `runtimeStatusStore.loadRuntimeStatusIfStale()` 在新鲜窗口内不会重复请求
- 超过窗口后会重新请求
- `AppShell` 在 `watchlist.movement` 与 `stream.keepalive` 事件后会触发节流刷新入口

## Expected Outcome

完成后，壳层 runtime 指标会在系统活跃事件后自动变新，而不会退回到固定轮询；同时 `/api/stream/status` 仍维持单一入口和受控频率。
