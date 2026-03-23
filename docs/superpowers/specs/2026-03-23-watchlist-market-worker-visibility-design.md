# Watchlist Market Worker Visibility Design

## Context

后端已经把独立 `market-worker` 的运行状态暴露到了 `/api/stream/status`，但当前前端还没有消费这部分信息。结果是：

- Watchlist 页面如果看到旧快照或 `unavailable`
- 用户仍然不知道是 worker 没启动、最近失败，还是只是数据暂时空缺

本轮目标是在 Watchlist 页面直接显示 market worker 的运行状态。

## Options

### Approach A: 在 Watchlist 页面局部展示

`watchlistStore` 在加载 watchlist 时顺手拉 `/api/stream/status`，页面顶部展示一个小型状态卡。

优点：

- 改动局部，风险最小
- 信息和业务场景直接对齐

缺点：

- 其他页面暂时看不到该状态

### Approach B: 在全局壳层展示

把 worker 状态放到 `AppShell` 顶部或侧边导航。

优点：

- 全局可见

缺点：

- 需要更广泛的 store/布局改造
- 对当前问题来说过大

## Recommended Design

采用 Approach A。

### Data Flow

- `watchlistStore.loadWatchlist()` 在加载自选股列表和行情后，再拉一次 `apiClient.getStreamStatus()`
- 只提取其中的 `market_worker`
- 存入 watchlist store 的局部状态

### UI

在 Watchlist 页顶部异动横幅附近新增一个轻量状态面板，至少展示：

- worker 状态：`ok` / `degraded` / `unknown`
- 最近成功时间
- 最近错误（有则展示）
- 最近产出 quotes 数

视觉上保持当前终端中间态，不引入新的复杂组件体系。

### Fallback Behavior

- 接口失败或 mock 降级时，仍显示一个可用的默认状态文案
- 不阻塞 watchlist 主数据加载

### Testing

覆盖：

- store 会拉取并保存 `market_worker`
- WatchlistView 渲染状态文案和错误提示

## Expected Outcome

完成后，用户打开 Watchlist 页面就能知道“行情 worker 是否活着、最近一次成功是什么时候、是不是刚失败过”，不再需要手工排查后端状态接口。
