# Latest Events 精简警报与手动抓取设计

日期：2026-08-03  
状态：已实现并验证

## 背景与目标

当前 Latest Events 页面和全局壳层同时展示多组运行状态：页面内 Runtime 警报、Raw Stream 说明标题，以及主内容区顶部的 SSE / Last event 状态条。这些信息挤占首屏，但用户当前只需要事件、主题和新闻内容。

本次目标：

- 移除截图所示的三组前端状态/说明 UI，但不删除底层 SSE、运行状态轮询和新闻列表能力；
- 在 Latest Events 页头加入“手动抓取新闻”入口；
- 复用现有 `POST /api/news/refresh?async_mode=true`、60 秒冷却和 `isRefreshing` 状态，不新增后端接口；
- 保持事件胶囊、主题 chips、筛选、新闻卡片、增量入流和抽屉阅读行为不变。

## 交互与视觉方案

采用克制的终端工作台风格：减少持续占位的告警面板，把唯一主动操作收敛到页面标题右侧。

1. 页头右侧保留 stale 标记，并新增手动抓取按钮。
2. 默认文案为“抓取最新新闻”；请求被接受后显示“抓取中”，按钮禁用并带旋转指示。
3. 请求被接受时显示轻量成功反馈；请求失败或命中冷却时提示稍后重试。反馈使用 `aria-live`，不再增加大面积告警卡。
4. 删除 Latest Events 内的 Runtime `StatusBanner`。
5. 删除 Raw Stream 的 eyebrow、标题和说明，仅保留新闻流内容容器。
6. 删除 AppShell 主内容顶部的 SSE / Last event / Workspace 状态条。侧栏现有系统状态区保留，避免彻底丢失诊断入口。

## 数据流

点击按钮调用 `newsStore.refreshNews()`：

`NewsFeedView -> newsStore.refreshNews -> apiClient.refreshNews -> POST /api/news/refresh?async_mode=true`

后端返回 202 后，store 进入 `isRefreshing=true`；后续 `news.created` SSE 会把新条目增量写入 feed 并清除刷新态，15 秒安全超时用于没有新条目时恢复按钮。现有 60 秒冷却阻止重复抓取。

## 测试与验收

- `NewsFeedView.test.ts`：三组截图 UI 不再出现；按钮存在；点击触发 store；抓取中禁用；成功/失败反馈正确。
- `AppShell.test.ts`：主内容顶部状态条不再渲染，侧栏系统状态仍存在。
- 前端专项测试、全量 Vitest、`npm --prefix frontend run build`、`git diff --check`。

## 风险与边界

- 异步抓取接口只表示任务已接受，不保证立即产生新新闻；反馈文案应表达“已开始抓取”，不能表达“已抓到新闻”。
- `refreshNews()` 的 `false` 同时可能代表请求失败、开发 mock 降级或冷却期；本次统一提示“暂未启动，请稍后重试”，不虚构具体原因。
- 不调整后端抓取频率、来源配置、SSE 连接和侧栏系统健康信息。
