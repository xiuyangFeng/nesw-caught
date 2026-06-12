# Runtime Diagnostics And Action Guidance Design

## Context

当前前端已经具备较完整的 runtime 可观测基础：

- `runtimeStatusStore` 统一读取 `/api/stream/status`
- `AppShell` 能展示 `SSE` 与 `market_worker` 状态
- `Watchlist` 能展示 worker 状态并提供“立即刷新一轮”动作
- runtime 快照支持事件驱动补刷与空闲期低频轮询

但界面仍停留在“字段罗列”层面。用户虽然能看到 `degraded`、`last_error`、`last_success_at`，却还需要自己推断：

- 到底是 `SSE` 断了，还是 `market-worker` 挂了
- 当前状态是“需要观察”还是“需要立即处理”
- 下一步该去哪里、做什么

这会让 runtime 面板的可操作性偏弱，尤其在出现 `degraded`、空心跳、worker 未上报等场景时更明显。

## Options

### Approach A: 在组件内继续拼接文案

分别在 `AppShell` 和 `Watchlist` 内用更多 `computed` 拼出诊断标题、详情和建议动作。

优点：

- 改动快

缺点：

- 规则会散落在多个组件
- 后续新增状态分支时容易不一致

### Approach B: 提取共享 runtime 诊断层

新增一个纯前端 utility，把 `connectionState`、`streamStatus`、`marketWorkerStatus`、`lastLoadedAt` 等信息归一成一个有限诊断结果，再由 `AppShell` 和 `Watchlist` 只负责展示。

优点：

- 规则集中，测试边界清楚
- 两个面板不会各说各话
- 后续若新增 `runtime.updated` 或更多 runtime 字段，也只需要收口在一处

缺点：

- 需要先定义一层归一语义

### Approach C: 继续增强后端字段，再让前端原样展示

优点：

- 从源头携带更多信息

缺点：

- 当前问题主要在前端解释层，而不是字段缺失
- 会把一个前端交互优化任务扩展成接口设计任务

## Recommended Design

采用 Approach B。

### Shared Diagnostic Model

新增 `frontend/src/utils/runtimeDiagnostics.ts`，输出类似下面的归一结果：

- `tone`: `success | warning | danger | default`
- `headline`: 当前最值得用户理解的一句话
- `detail`: 解释发生了什么
- `actionLabel`: 建议动作文案
- `actionTarget`: `watchlist | stream | none`

归一优先级按“最需要操作的问题先说”：

1. `SSE` 离线
2. 当前使用 mock / degraded stream
3. `market_worker` 没有 runtime 状态
4. `market_worker` 最近失败
5. `market_worker` 心跳或成功时间明显陈旧
6. 否则视为健康

### Shell Behavior

`AppShell` 继续保留现有紧凑状态 badge，但在 `Market worker` 区块补充：

- 归一后的诊断标题
- 一条短解释
- 一条建议动作

如果建议动作指向 `watchlist`，则直接提供进入 `/watchlist` 的轻量链接，让全局壳层不只是“显示故障”，还能引导用户走到处理页面。

### Watchlist Behavior

`WatchlistView` 的 worker 面板继续保留“立即刷新一轮”按钮，但新增：

- 与壳层一致的诊断标题
- 更明确的处理建议
- 在 `degraded` 或 `stale` 场景下，把现有按钮解释成推荐动作，而不是孤立按钮

也就是说，Watchlist 负责“可执行动作”，AppShell 负责“全局预警 + 导航”。

### Staleness Heuristic

前端以 runtime 快照内的时间字段做近似判断：

- 优先看 `last_success_at`
- 若为空则回退到 `last_heartbeat_at`
- 超过 10 分钟视为陈旧

这不是严格 SLA，而是 UI 诊断阈值，目的是帮助用户识别“worker 可能卡住”。

### Testing

按 TDD 覆盖三层：

- `runtimeDiagnostics` utility：离线、worker 缺失、worker 失败、worker 陈旧、健康
- `AppShell`：展示诊断标题与跳转建议
- `WatchlistView`：展示诊断标题，并把“立即刷新一轮”解释为推荐动作

## Expected Outcome

完成后，用户不再需要自己解读零散 runtime 字段，而是能直接看到：

- 现在是哪一类问题
- 为什么这样判断
- 下一步应该去哪儿、做什么

这能明显提高 runtime 面板的可用性，同时不改变任何后端接口。
