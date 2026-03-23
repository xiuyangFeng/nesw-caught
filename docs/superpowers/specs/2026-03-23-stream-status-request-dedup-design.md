# Stream Status Request Dedup Design

## Context

上一轮已经把前端运行时健康状态抽到了独立 `runtimeStatusStore`，但 `AppShell` 启动时仍会同时调用：

- `connectionStore.loadStreamStatus()`
- `runtimeStatusStore.loadRuntimeStatus()`

这两个调用都会请求同一个 `/api/stream/status`，导致：

- 前端在启动阶段重复请求同一接口
- `connectionStore` 和 `runtimeStatusStore` 共同拥有 stream status 读取职责
- 后续如果增强 runtime 轮询或错误处理，状态同步边界仍然模糊

本轮目标是把 `/api/stream/status` 的读取职责完全收口到 `runtimeStatusStore`，让 `connectionStore` 只负责连接状态机和 `SSE` 生命周期。

## Options

### Approach A: `runtimeStatusStore` 负责请求，`connectionStore` 接收已读取快照

`runtimeStatusStore` 继续唯一请求 `/api/stream/status`，并额外暴露 `usingMock`。`connectionStore` 增加一个同步入口，用于接收已读取的 stream status 快照并更新连接初始状态。

优点：

- 请求入口唯一
- `connectionStore` 职责收敛为连接状态机
- 改动范围小，不影响现有页面消费

缺点：

- 需要在 `AppShell.bootstrap()` 中明确排一下初始化顺序

### Approach B: 改为 `connectionStore` 唯一请求，再把结果回填给 `runtimeStatusStore`

优点：

- 不需要新增 `connectionStore` 的同步入口

缺点：

- 让运行时状态 store 反过来依赖连接 store，边界更差

### Approach C: 合并两个 store

优点：

- 理论上请求最容易去重

缺点：

- 会把 `SSE` 生命周期和后台 worker/runtime 面板重新揉回一个 store，违背上一轮刚整理好的职责边界

## Recommended Design

采用 Approach A。

### Store Responsibilities

`runtimeStatusStore`：

- 唯一请求 `/api/stream/status`
- 保存 `streamStatus`
- 保存 `marketWorkerStatus`
- 保存 `usingMock`
- 保存 `loading`、`error`、`lastLoadedAt`

`connectionStore`：

- 保存连接状态 `state`
- 保存 `lastEventAt`
- 保存 `streamError`
- 保存 `isConnectionStale`
- 提供 `applyStreamStatus(streamStatus, usingMock)` 同步入口
- 管理 `connect()` / `disconnect()`

### Bootstrap Flow

`AppShell.bootstrap()` 调整为：

1. `runtimeStatusStore.loadRuntimeStatus()`
2. `connectionStore.applyStreamStatus(runtimeStatusStore.streamStatus, runtimeStatusStore.usingMock)`
3. 其余 store 并行加载
4. 调用 `connectionStore.connect()`

这样初始化阶段只会发生一次 `/api/stream/status` 请求。

### Testing

按 TDD 覆盖：

- `runtimeStatusStore` 记录 `usingMock`
- `connectionStore.applyStreamStatus()` 能根据快照更新连接初始状态
- `AppShell` 启动时不再调用 `connectionStore.loadStreamStatus()`
- `AppShell` 会在 runtime 状态加载后把快照同步给 `connectionStore`

## Expected Outcome

完成后，前端对 `/api/stream/status` 的读取会有且只有一个入口；`runtimeStatusStore` 负责 runtime 快照，`connectionStore` 负责连接状态机，两者边界清楚且没有重复请求。
