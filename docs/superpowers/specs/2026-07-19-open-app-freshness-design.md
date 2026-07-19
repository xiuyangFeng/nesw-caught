# 打开 App 即时刷新设计

日期：2026-07-19
状态：已与用户确认（策略、刷新方式均已选定；用户已授权使用子智能体进行后续开发）

## 背景与目标

用户反馈新闻信息有滞后：不是 7x24 挂着这个项目，而是想在打开时能立刻看到最新抓取的消息。

现状排查（详见对话记录，关键代码位置）：

- 后台常驻调度器 `NewsIngestScheduler`（`backend/app/services/news_ingest_scheduler.py`）默认关闭（`news_scheduler_enabled=False`，`backend/app/core/config.py:31`），且用户明确表示本地机器不想常驻定时任务（担心占用内存/CPU）。
- 后端已有现成的手动刷新入口 `POST /api/news/refresh`（`backend/app/api/routes/news.py:65-97`），支持 `async_mode=true`（`BackgroundTasks` 异步执行，立即返回 202），有 60 秒冷却锁（`news_refresh_lease.py`）防止滥用。
- `NewsIngestionService.refresh_all()`（`backend/app/services/ingestion/service.py:35`）已经用线程池并发抓取全部源，并带 ETag/Last-Modified 缓存（未变更的源走 304，几乎零开销），单源健康状态（含 `last_success_at`）已持久化在 `SourceHealth` 表（`backend/app/models/source_health.py`）。
- **真正的缺口只在前端**：`AppShell.vue` 的 `bootstrap()`（`frontend/src/components/layout/AppShell.vue:274-294`）只读取 DB 里已有数据，从未调用刷新接口；`newsStore.refreshNews()`（`frontend/src/stores/newsStore.ts:302`）虽然存在但没有任何组件调用它，且调用的是同步模式（未传 `async_mode=true`）。

用户决策记录：

- 不开启后台常驻调度器，只依赖"打开 App 时触发抓取"。
- 触发抓取时用异步刷新（先展示已有数据，抓取在后台跑，跑完通过现有事件推送增量更新），不做同步等待。
- 前台停留期间应周期性自动补抓（默认方案，用户未反对），标签页隐藏时暂停以节省资源。

## 设计

### 1. 触发时机与方式

- `AppShell.vue` 的 `bootstrap()` 中，在读取本地数据的同时（不等待、不阻塞）触发一次 `newsStore.refreshNews()`。
- `apiClient.refreshNews()`（`frontend/src/api/client.ts:224`）改为请求 `POST /api/news/refresh?async_mode=true`，服务端立即返回 202，真正抓取在后台线程跑。
- 抓取产生的新条目通过既有事件总线推送：`refresh_all()` 对每条新插入条目都发布一个 `news.created` 事件（`backend/app/services/ingestion/service.py`），已经走 SSE 推给前端（`connectionStore.connect`，`AppShell.vue:295-329`），并由 `newsStore.upsertNews` 增量更新到列表，因此刷新完成后**不需要**额外轮询或整页重新拉取。`news.created_batch` 是后端内部事件（用于路由缓存失效等），SSE 层不转发给前端，前端无需监听。

### 2. 前台周期性补抓

- 新增一个可见性感知的定时器：页面处于前台（`document.visibilityState === 'visible'`）时，每 5 分钟触发一次 `newsStore.refreshNews()`；页面被隐藏/最小化时清除定时器；重新变为可见时立即补发一次刷新并重启定时器。
- 复用现有 60 秒冷却（客户端 `REFRESH_COOLDOWN_MS` + 服务端 lease），短时间内来回切换标签页不会触发重复抓取，静默跳过（返回 `false`，不报错、不提示）。

### 3. 刷新状态指示

- `newsStore` 新增 `isRefreshing` 响应式状态：发起异步刷新时置 `true`；在以下任一条件发生时置 `false`：
  - 触发之后收到的第一个 `news.created` / `news.created_batch` 事件；
  - 触发后 15 秒超时（兜底，覆盖"这轮抓取没有新内容"的情况）。
- UI 上在现有连接状态指示位置（`connectionStore` 附近）增加一个小型 spinner/文案（如"同步中"），非阻塞、不遮挡内容。

### 4. 不改动的部分

- 后台常驻调度器保持默认关闭，不新增开关逻辑。
- 后端 `refresh_all()`、ETag 缓存、`SourceHealth` 持久化、冷却锁机制均已满足需求，不做后端改动。
- 手动刷新按钮（如果 UI 上已有）行为不变，只是底层改用 async_mode。

## 影响范围

仅前端三个文件：

- `frontend/src/api/client.ts` —— `refreshNews()` 请求参数改为 `async_mode=true`。
- `frontend/src/stores/newsStore.ts` —— 新增 `isRefreshing` 状态；`refreshDashboardNews()` 适配异步语义（不再依赖响应体里的抓取结果来 `loadDashboardNews`，改为依赖 SSE 增量 + 超时兜底清除 `isRefreshing`）。
- `frontend/src/components/layout/AppShell.vue` —— `bootstrap()` 中触发首次刷新；新增可见性感知的周期性刷新定时器（模式参考已有的 `startFeedLayoutPolling`/`startRuntimeStatusPolling`）。

不涉及数据库迁移、API 契约变更、后端调度器改动。

## 测试计划

- 前端单测：`newsStore.test.ts` 补充 `isRefreshing` 状态流转（触发→收到事件清除、触发→超时清除、冷却期内静默跳过）。
- 手动验证：本地起后端+前端，冷启动打开页面观察 Network 面板出现 `POST /api/news/refresh?async_mode=true` 请求且立即 202 返回；等待期间页面不阻塞；新条目到达时列表增量更新且 spinner 消失；切换标签页隐藏/显示验证定时器暂停/恢复。
