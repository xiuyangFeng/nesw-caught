# Runtime Status Low Frequency Polling Design

## Context

当前前端 runtime 状态已经收口到 `runtimeStatusStore`，并通过两条路径保持新鲜：

- 应用启动时主动加载一次 `/api/stream/status`
- `watchlist.movement` 和 `stream.keepalive` 等关键 `SSE` 事件到达后，按 15 秒窗口节流补刷一次

这套机制在“系统活跃”时已经足够，但仍有一个明显缺口：如果后台 runtime 状态发生变化，而系统长时间没有相关 `SSE` 事件，壳层中的 `market_worker` 摘要和 stream backend 摘要不会自动前进。

本轮目标是补齐这个 idle 场景，同时保持当前架构边界：

- `SSE` 继续负责业务事件流
- `/api/stream/status` 继续负责 runtime 快照
- 新增能力尽量落在 `runtimeStatusStore`，避免把刷新策略散落到组件层

## Options

### Approach A: 在现有事件驱动方案上增加低频轮询

由 `AppShell` 在挂载后启动一个低频定时器，定期调用 `runtimeStatusStore.loadRuntimeStatusIfStale()`。该入口继续由 store 负责并发保护和新鲜度判断。

优点：

- 直接补齐“长时间无事件但后台状态变化”的场景
- 与现有 store API 和请求收口方向一致
- 改动集中在前端，接口契约不变

缺点：

- 会多出固定频率的状态请求

### Approach B: 把 runtime 摘要并入现有 `SSE` 事件负载

优点：

- 理论上可以减少额外的状态请求

缺点：

- 要扩展后端事件契约，而不只是前端策略调整
- 需要决定哪些事件携带 runtime、何时采样、是否全量附带，边界会重新变复杂
- 会让 `SSE` 事件层承担 runtime 快照职责，和当前分层相冲突

### Approach C: 保持现状，仅依赖事件驱动补刷

优点：

- 不增加任何额外请求或定时器

缺点：

- 不能解决 idle 场景的状态陈旧问题

## Recommended Design

采用 Approach A。

### Polling Strategy

在 `AppShell` 中新增一个低频轮询定时器：

- 组件挂载并完成 bootstrap 后启动
- 组件卸载时清理
- 定时间隔默认 60 秒

轮询回调不直接调用 `loadRuntimeStatus()`，而是调用已有的 `loadRuntimeStatusIfStale()`。这样固定轮询与事件驱动刷新共用同一套新鲜度和并发控制，不会出现两套规则互相打架。

### Store Responsibilities

`runtimeStatusStore` 继续作为 `/api/stream/status` 的唯一读取入口，并保留：

- `loading` 并发保护
- `lastLoadedAt` 新鲜度判断
- `loadRuntimeStatusIfStale(maxAgeSeconds = 15)` 这一节流入口

为了让轮询频率和“数据是否值得刷新”分离，轮询调用时显式传入更长的 freshness window，例如 45 秒。结果是：

- 即使保留 60 秒定时器，也不会和事件驱动的 15 秒窗口冲突
- 若事件刚刚触发过补刷，下一次轮询通常会被 store 内的新鲜度判断直接跳过

### Component Boundary

轮询生命周期放在 `AppShell`，而不是 store 内部：

- 只有全局壳层存在时才轮询
- 不引入全局常驻 timer 副作用
- 组件仍只负责编排“何时触发”，不负责判断“是否真的要请求”

### Testing

按 TDD 覆盖：

- `AppShell` 在 bootstrap 后注册轮询，并在定时器触发时调用 `runtimeStatusStore.loadRuntimeStatusIfStale(45)`
- 卸载时会清理定时器
- 既有 `watchlist.movement` / `stream.keepalive` 事件驱动补刷行为保持不变

## Expected Outcome

完成后：

- 系统活跃时，runtime 仍靠关键 `SSE` 事件快速补刷
- 系统空闲时，壳层会通过低频轮询把 runtime 快照缓慢推进
- 不需要改后端 `SSE` 事件契约，也不需要新增 runtime 专用事件
