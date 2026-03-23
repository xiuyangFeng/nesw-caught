# 代码变更记录

> 用于记录本项目每一次实际修改。新增记录时，追加到最上方。

## 2026-03-23 18:51

- 修改人：Codex
- 修改范围：runtime 诊断提示与建议动作收口
- 变更内容：新增前端 `runtimeDiagnostics` 归一化工具，把 `SSE` 连接状态、stream 降级状态和 `market_worker` runtime 状态统一映射成少量诊断结果；`AppShell` 现在除了展示原始 badge，还会给出当前 runtime 问题的一句话诊断、解释和建议动作，并在 worker 故障/陈旧场景下直接引导用户打开 Watchlist；`WatchlistView` 的 worker 面板也复用同一套诊断结果，把现有“立即刷新一轮”按钮解释成推荐动作，而不再只是孤立按钮。这样用户看到 `degraded`、未上报或陈旧状态时，不需要自己拼字段理解下一步该做什么。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/runtimeDiagnostics.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/runtimeDiagnostics.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-runtime-diagnostics-actions-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-runtime-diagnostics-actions-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口或前端 API 字段；仅新增前端内部 runtime 诊断归一层
- 验证情况：`npm --prefix frontend run test -- --run src/utils/runtimeDiagnostics.test.ts src/components/layout/AppShell.test.ts src/views/WatchlistView.test.ts src/stores/runtimeStatusStore.test.ts src/stores/watchlistStore.test.ts` 通过（5 个文件 / 21 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前诊断层仍基于前端时间阈值和已有快照字段做启发式判断，例如把 10 分钟无成功/心跳视为陈旧；这提升了可操作性，但不是严格运维告警。如果后续需要更精确的故障分类，应再考虑后端提供专门的 runtime reason code

## 2026-03-23 18:05

- 修改人：Codex
- 修改范围：AppShell 空闲期 runtime 低频轮询
- 变更内容：在保留现有关键 `SSE` 事件节流补刷的基础上，为 `AppShell` 增加 60 秒一次的低频 runtime 轮询；轮询本身不直接请求接口，而是统一走 `runtimeStatusStore.loadRuntimeStatusIfStale(45)`，继续由 store 负责新鲜度判断与并发保护。这样当系统长时间没有 `watchlist.movement` 或 `stream.keepalive` 时，壳层中的 `market-worker` 与 stream runtime 摘要仍会缓慢更新，而不需要改后端 `SSE` 事件契约。同时补上壳层卸载保护，避免异步 bootstrap 在组件销毁后迟到启动轮询或继续留下悬空 timer。同步补充组件测试，覆盖轮询启动、触发、卸载清理和“先卸载后完成初始化”的边界行为。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-runtime-status-low-frequency-polling-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-runtime-status-low-frequency-polling-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或字段；前端仅增加壳层轮询编排，继续复用既有 `GET /api/stream/status`
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 8 个用例）；`npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/components/layout/AppShell.test.ts src/stores/connectionStore.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（5 个文件 / 17 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 runtime 新鲜度仍然是 best-effort；空闲期最多可能滞后约 60 秒，且数据源仍是快照接口而非真正 push 的 runtime 事件。如果后续需要更细粒度的实时可观测性，再评估新增独立 `runtime.updated` 事件，而不是把摘要硬塞进现有业务 `SSE` 载荷

## 2026-03-23 16:10

- 修改人：Codex
- 修改范围：runtime 状态在关键 `SSE` 事件后做节流刷新
- 变更内容：在 `runtimeStatusStore` 中新增 `loadRuntimeStatusIfStale()`，把 runtime 快照刷新节流逻辑收口到 store 内，默认按 15 秒窗口控制；`AppShell` 现在会在 `watchlist.movement` 和 `stream.keepalive` 事件后触发该入口，使壳层中的 `market-worker` 与事件层 runtime 指标会在系统活跃时自动变新，而不需要引入固定轮询。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-runtime-status-event-refresh-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-runtime-status-event-refresh-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；前端仅增加 runtime store 的节流刷新入口，事件驱动地再次读取既有 `/api/stream/status`
- 验证情况：`npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/components/layout/AppShell.test.ts src/stores/connectionStore.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（5 个文件 / 15 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 runtime 刷新仍依赖启动、人工动作和关键 `SSE` 事件；如果系统长时间无事件但后台状态发生变化，壳层仍不会立即感知。下一阶段若要进一步提升实时性，可以再评估低频轮询或后端直接把 runtime 摘要塞进 `SSE` 事件

## 2026-03-23 16:05

- 修改人：Codex
- 修改范围：前端 `/api/stream/status` 请求去重与连接状态收口
- 变更内容：把 `/api/stream/status` 的唯一读取入口正式收口到 `runtimeStatusStore`，新增 `usingMock` 持久化；`connectionStore` 去掉直接请求接口的职责，改为通过 `applyStreamStatus()` 接收 runtime 快照，只负责 `SSE` 连接状态机与事件生命周期；`AppShell` 启动时先加载 runtime 状态，再把快照同步给 `connectionStore`，从而消除此前启动阶段对同一状态接口的双请求。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/connectionStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/connectionStore.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-stream-status-request-dedup-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-stream-status-request-dedup-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口；前端 store 职责调整为 `runtimeStatusStore` 唯一读取 `/api/stream/status`，`connectionStore` 不再直接发起该请求
- 验证情况：`npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/stores/connectionStore.test.ts src/components/layout/AppShell.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（5 个文件 / 12 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 runtime 快照仍是启动时和显式动作后刷新，不会随着 `SSE` 事件自动回填；如果后续希望壳层 runtime 指标更实时，需要再决定是增加轮询，还是在特定 `SSE` 事件后触发轻量刷新

## 2026-03-23 15:43

- 修改人：Codex
- 修改范围：前端运行时状态抽离为独立 `runtimeStatusStore`
- 变更内容：新增独立 `runtimeStatusStore` 统一承接 `/api/stream/status` 和 `market_worker` 运行状态，`AppShell` 与 Watchlist 页面改为直接消费该 store；`watchlistStore` 不再在 `loadWatchlist()` 中顺手请求 runtime 状态，只保留自选股业务数据与手动刷新结果，并在人工“立即刷新一轮”成功后联动刷新 runtime store。这样全局壳层不再依赖 watchlist 数据加载副作用才能看到 worker 健康状态，前端运行时基础设施状态和业务状态边界也更清晰。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/runtimeStatusStore.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-runtime-status-store-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-runtime-status-store-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口；前端状态结构调整为新增独立 `runtimeStatusStore`，`watchlistStore` 不再持有 `marketWorkerStatus`
- 验证情况：`npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/stores/watchlistStore.test.ts src/components/layout/AppShell.test.ts src/views/WatchlistView.test.ts` 通过（4 个文件 / 11 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 `connectionStore` 与 `runtimeStatusStore` 仍会分别请求一次 `/api/stream/status`，虽然职责已经分清，但请求层尚未去重；如果后续继续增强 runtime 面板或轮询逻辑，建议把 SSE 连接摘要与 runtime 接口读取再进一步收口

## 2026-03-23 14:50

- 修改人：Codex
- 修改范围：`AppShell` 系统状态卡片指标对齐修复
- 变更内容：先将左下角 `System Status` 卡片中的两条状态头从 `flex justify-between` 改为统一的布局约束，随后根据实际 UI 继续收敛为纵向 stack：标签在上、badge 独占下一行整宽区域。这样 `SSE 已断开`、`market_quote_producer ok` 之类长状态文案不再和左侧标签争抢同一行宽度，`Market worker` 也不会被挤成难看的断行；同时补充测试锚点并在 `AppShell` 组件测试中锁定 stack 布局和整宽 badge 约束。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-app-shell-status-indicator-alignment-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-app-shell-status-indicator-alignment-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-app-shell-status-badge-stacking-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-app-shell-status-badge-stacking-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无，仅调整前端模板布局和测试约束
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前修复优先保证侧栏稳定和可读性，因此 badge 改成了整宽堆叠展示；如果后续希望恢复更紧凑的横向信息密度，需要在更宽侧栏或更短文案前提下重新设计

## 2026-03-23 14:33

- 修改人：Codex
- 修改范围：Watchlist 展示最近一次手动刷新结果
- 变更内容：在 `watchlistStore` 中新增 `lastManualRefreshResult`，手动执行“立即刷新一轮”成功后会保留本次操作返回的 `quotes_count`、`symbols` 与 `triggered_at`；Watchlist 页的 `market-worker` 状态面板现在会直接显示最近一次人工刷新时间、刷新标的数量和 symbol 列表。这样用户除了看到 worker 健康状态，也能知道刚刚那次人工重试到底有没有生效。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-manual-refresh-result-visibility-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-manual-refresh-result-visibility-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；前端仅复用已有 `POST /api/market/refresh` 返回结果做本地状态展示
- 验证情况：`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（2 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过；`conda run -n news-caught pytest backend/tests -q` 通过（94 个用例）
- 风险/后续事项：该结果只保存在当前前端会话内，刷新页面后会丢失；如果后续需要跨页面或跨会话保留人工操作历史，应再补后端持久化审计记录

## 2026-03-23 14:21

- 修改人：Codex
- 修改范围：自选股行情人工“立即刷新一轮”闭环
- 变更内容：新增后端显式运维接口 `POST /api/market/refresh`，用于在独立 `market-worker` 之外人工触发一次同步行情刷新，并继续发布既有 `market.watchlist_refreshed` 事件；前端 `watchlistStore` 增加 `refreshMarketQuotes()`，Watchlist 页面状态面板新增“立即刷新一轮”按钮、加载态和失败提示。这样当用户看到 worker `degraded` 或行情滞后时，可以直接在 UI 上触发一次人工重试，而不需要切回终端。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-manual-market-refresh-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-manual-market-refresh-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增 `POST /api/market/refresh`，返回 `quotes_count`、`symbols`、`triggered_at`；前端开始消费该接口作为显式人工运维动作
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market.py -q` 通过（8 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（2 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过；`conda run -n news-caught pytest backend/tests -q` 通过（94 个用例）
- 风险/后续事项：该接口会在 Web 进程里执行一次同步行情拉取，因此应被视为人工重试工具，而不是日常生产路径；如果后续需要更纯粹的架构边界，可以再把“refresh now” 改成发命令给独立 worker 执行

## 2026-03-23 14:07

- 修改人：Codex
- 修改范围：全局壳层展示 `market-worker` 健康状态
- 变更内容：在 `AppShell` 的 `System Status` 面板中复用 `watchlistStore.marketWorkerStatus`，新增全局可见的 `market-worker` 状态摘要，展示 worker 名称、健康状态、最近成功时间和最近错误。这样无论用户停留在哪个页面，都能直接看到行情生产链路是否处于 `ok` 或 `degraded`。本次不新增请求，也不引入新的全局状态中心，完全复用现有 watchlist 加载链路。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-app-shell-market-worker-visibility-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-app-shell-market-worker-visibility-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；前端仅把已有 `watchlistStore.marketWorkerStatus` 上提到全局壳层展示
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前全局壳层仍依赖 `watchlistStore.loadWatchlist()` 完成后才有 `market-worker` 状态；如果后续想把运行状态完全独立于自选股数据加载，需要再抽离专门的 runtime store

## 2026-03-23 14:01

- 修改人：Codex
- 修改范围：Watchlist 页面展示 `market-worker` 运行状态
- 变更内容：扩展前端 `StreamStatus` 类型与 `watchlistStore`，在加载自选股列表时顺手拉取 `/api/stream/status` 并缓存其中的 `market_worker` 状态；`WatchlistView` 顶部新增一个轻量状态面板，直接展示独立行情 worker 的名称、当前状态、最近成功时间、最近产出 quotes 数和最近错误。这样当页面出现旧快照或 `unavailable` 时，用户能直接在 watchlist 页面判断是不是 worker 未启动或刚刚失败。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-watchlist-market-worker-visibility-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-watchlist-market-worker-visibility-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；前端开始消费现有 `GET /api/stream/status` 响应中的 `market_worker` 字段
- 验证情况：`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（2 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前状态面板只显示在 Watchlist 页面，其他页面仍看不到 worker 健康度；如果后续想把可观测性做成全局能力，可以再把这部分上提到壳层或共享状态中心

## 2026-03-23 13:55

- 修改人：Codex
- 修改范围：本地开发入口自动托管 `market-worker`
- 变更内容：更新 `scripts/dev.sh`，让 `make dev` 在启动后端和前端的同时自动启动独立自选股行情 worker，并把 `MARKET_WORKER_PID` 纳入统一的清理与存活检测逻辑；这样任一子进程退出都会触发整体退出，`Ctrl+C` 也会一并停止三个进程。同步补充脚本回归测试，并更新 README 中 `make dev` 的说明。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/scripts/dev.sh`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_dev_launcher.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-dev-launcher-market-worker-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-dev-launcher-market-worker-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；仅本地开发启动行为变化，`make dev` 现在默认同时拉起 backend、frontend 和 `market-worker`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_dev_launcher.py -q` 通过（1 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（93 个用例）
- 风险/后续事项：当前 `make dev` 会多一个长期运行进程和更多终端输出；如果后续再接入新闻 worker 或更多后台任务，建议统一抽象成更清晰的本地 supervisor，而不是继续在 shell 脚本中线性堆叠

## 2026-03-23 13:42

- 修改人：Codex
- 修改范围：独立 market worker 可观测性与状态接口扩展
- 变更内容：新增数据库表 `worker_runtime_status` 和对应仓储，由 `MarketQuoteProducer` 在每轮刷新后持久化 heartbeat、成功/失败计数、最近错误和最近产出 quotes 数；`/api/stream/status` 现在会额外返回 `market_worker` 区块，展示独立 `market_quote_producer` 的运行状态。这样 Web API 即使与 worker 分进程运行，也能直接看到行情 worker 是否正常工作。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/worker_runtime_status.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/worker_runtime_status_repository.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/market_quote_producer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market_quote_producer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stream_status.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-market-worker-observability-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-market-worker-observability-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/stream/status` 响应新增可选 `market_worker` 字段，包含独立行情 worker 的 `name`、`status`、最近 heartbeat/成功/失败时间、最近错误、`cycle_count`、`success_count`、`failure_count`、`last_quotes_count`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market_quote_producer.py backend/tests/test_stream_status.py -q` 通过（9 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（92 个用例）
- 风险/后续事项：当前状态存储依赖应用数据库，适合本地和单库部署；如果后续把 worker 与 Web 拆到多数据库或跨区域部署，需要再定义统一的运行状态源或集中监控出口

## 2026-03-23 13:18

- 修改人：Codex
- 修改范围：自选股行情 producer 独立 worker 化
- 变更内容：将上一轮仍挂在 FastAPI `lifespan` 里的 `MarketQuoteProducer` 提取为独立 worker 入口 `python -m app.workers.market_quote_producer`，worker 启动时负责初始化数据库、构建事件总线、注册 `market.watchlist_refreshed` 的本地阈值提醒订阅者，并阻塞运行行情 producer；Web 应用启动流程不再持有或启动行情 producer，只保留 API 和新闻相关事件处理。同步补充 worker 入口测试、Web 不再启动 producer 的生命周期测试，并新增 `make market-worker` 与 README 运行说明。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/workers/market_quote_producer.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/market_quote_producer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market_quote_producer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/Makefile`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-market-quote-worker-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-market-quote-worker-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：HTTP 接口和事件名不变；运行方式变化为需要显式启动独立 `market-worker` 才会连续生产自选股行情并触发阈值提醒
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market_quote_producer.py backend/tests/test_market.py -q` 通过（13 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（90 个用例）
- 风险/后续事项：当前 `make dev` 仍不会自动拉起 `market-worker`，开发环境若只启动前后端会看到 watchlist 维持旧快照或 `unavailable`；后续可考虑扩展 `scripts/dev.sh` 一并托管 worker，或给前端/状态接口增加更明确的 worker 存活提示

## 2026-03-23 02:10

- 修改人：Codex
- 修改范围：自选股行情生产者从请求链路迁移到后台 producer
- 变更内容：新增 `MarketQuoteProducer` 后台服务，在应用启动后按固定轮询间隔读取 watchlist、拉取真实行情、写入快照并发布 `market.watchlist_refreshed`；`QuoteService` 拆分为“主动刷新”和“缓存读取”两条路径，`/api/market/watchlist` 与 `/api/market/symbols/{symbol}` 不再在请求路径里同步触发上游行情拉取，只返回最近一次已生产的快照结果；同步补充 producer 生命周期测试、缓存读取路由测试、配置默认值测试，以及 README 中的运行说明与环境变量文档。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/market_quote_producer.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/quote_service.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market_quote_producer.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_event_bus.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-market-quote-producer-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-market-quote-producer-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：HTTP 接口路径和字段不变；`GET /api/market/watchlist` 与 `GET /api/market/symbols/{symbol}` 的职责从“请求时刷新并返回”变为“读取后台 producer 最近一次已生成的行情”；事件名 `market.watchlist_refreshed` 保持不变，但生产者从 route 迁移为后台任务
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market_quote_producer.py backend/tests/test_market.py backend/tests/test_event_bus.py backend/tests/test_stream_status.py -q` 通过（17 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（89 个用例）
- 风险/后续事项：当前仍是基于 `yfinance` 的轮询 producer，不是外部流式实时连接；应用进程重启后首次 producer 周期前可能短暂返回 `unavailable`/`quote not produced yet`，若后续需要更强实时性或多实例一致性，应继续把 producer 输入侧切到独立 worker 或 streaming provider

## 2026-03-23 00:54

- 修改人：Codex
- 修改范围：事件层第二阶段接入 `news.signals_processed`、通知批处理和行情刷新事件
- 变更内容：继续沿用 Redis 混合事件层，把原先散落在 route 内的副作用收束到统一事件契约上。`NewsSignalPipelineService.process_news_ids()` 现在返回处理摘要，应用启动时注册的 `news.created_batch` 订阅者在跑完信号流水线后继续发布 `news.signals_processed`；新闻分析路由不再直接调用通知服务，而是发布 `news.analysis_completed`；自选股行情路由不再在 route 内做阈值提醒，而是发布 `market.watchlist_refreshed`，再由本地订阅者结合 watchlist 阈值调用通知服务。这样后续接入真正实时行情源时，只要继续发布同名事件即可复用现有通知和处理链。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_signal_pipeline.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/event_bus.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_analysis.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-event-layer-stage2-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-event-layer-stage2-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增 HTTP 接口；事件层新增 `news.signals_processed`、`news.analysis_completed`、`market.watchlist_refreshed` 事件名；新增环境变量 `REDIS_STREAM_MARKET_WATCHLIST`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_event_bus.py backend/tests/test_news_ingestion.py backend/tests/test_news_analysis.py backend/tests/test_market.py backend/tests/test_feishu_notify.py -q` 通过（42 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（82 个用例）
- 风险/后续事项：当前行情仍是请求触发刷新而非真正的 WebSocket 实时流，`market.watchlist_refreshed` 只是先统一了事件契约；下一阶段若接入实时行情 provider，应优先让新 provider 直接向该事件入口发布批量行情，而不是再把逻辑写回 route

## 2026-03-23 00:42

- 修改人：Codex
- 修改范围：Redis 混合事件层第一阶段接入
- 变更内容：将原有仅支持进程内同步分发的 `EventBus` 升级为“Redis Streams 发布 + 本地总线兜底”的混合事件层，新增 Redis publisher 与事件层状态模型；`NewsIngestionService.refresh_all()` 现对新增新闻发布 `news.created_batch` 事件，由应用启动时注册的本地订阅者继续驱动 `NewsSignalPipelineService`，从而在保持现有业务语义和前端 `SSE` 展示不变的前提下，为后续多源异步化接入打下基础；同时扩展 `/api/stream/status` 返回真实事件层后端、Redis 可用性、最近事件和错误信息，并补充 README 中的 Redis 运行说明与环境变量。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/event_bus.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/redis_stream_bus.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_event_bus.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stream_status.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-redis-event-layer-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-redis-event-layer-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/stream/status` 响应增加 `backend`、`redis_enabled`、`last_published_at`、`last_event_name`、`last_error` 字段；原有 `mode` 与 `status` 仍保留
- 验证情况：`conda run -n news-caught pytest backend/tests/test_event_bus.py -q` 通过（4 个用例）；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_refresh_all_runs_signal_pipeline_for_inserted_items backend/tests/test_stream_status.py -q` 通过（2 个用例）；`conda run -n news-caught pytest backend/tests/test_health.py backend/tests/test_news_ingestion.py backend/tests/test_news_signal_pipeline.py backend/tests/test_market.py backend/tests/test_x_monitor.py backend/tests/test_event_bus.py backend/tests/test_stream_status.py -q` 通过（39 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（79 个用例）
- 风险/后续事项：当前 Redis 仅负责发布而非消费，严格来说仍是过渡态；下一阶段如需真正把 pipeline、通知或实时行情拆到独立 worker，可继续沿用当前事件名与 stream 命名扩展，而无需重改生产者接口

## 2026-03-22 23:56

- 修改人：Codex
- 修改范围：Redis Python 客户端依赖准备
- 变更内容：为后端后续接入 Redis 事件层预先补充 `redis` Python 客户端依赖，同时同步更新根目录 `requirements.txt` 与 `backend/pyproject.toml`，保证通过 `conda` 环境和可编辑安装两条路径都能获得一致依赖。本次不改动业务代码、数据库结构或运行逻辑，仅做环境准备。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/pyproject.toml`
  - `/Users/xiuyang/Desktop/news-caught/requirements.txt`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：已完成依赖清单更新；`conda run -n news-caught pip install redis` 成功，`conda run -n news-caught python -c "import redis; print(redis.__version__)"` 返回 `7.3.0`；Redis 系统安装仍在进行中
- 风险/后续事项：当前仅完成依赖声明，后续仍需在 `news-caught` conda 环境中执行安装，并补充 Redis 连接配置与事件流封装后才能真正投入使用

## 2026-03-22 22:11

- 修改人：Codex
- 修改范围：`Watchlist` / `WatchlistDetail` / `TopicDetail` 终端中间态收尾
- 变更内容：将剩余高频页面继续收敛到与 `AppShell`、`Dashboard`、`News Feed` 一致的“冷蓝底 + 橙色焦点”中间态。`Watchlist` 首页引入 `Control Station` 微标签，将左侧管理面板、候选列表、主操作按钮和右侧关联新闻统一为更硬的终端壳层；`WatchlistTable` 调整为更紧凑的终端表格并强化表头层级；`WatchlistDetail` 为核心行情区增加主监控模块，收紧指标卡与相关新闻卡；`TopicDetail` 则把主题摘要卡、过滤工具条和来源分组卡收敛为更像分析工作台的面板。全程不改动数据加载、过滤语义、跳转行为或任何 API / store 契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-22-watchlist-suite-terminal-midstate-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-22-watchlist-suite-terminal-midstate-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅展示层和测试锚点调整，未改动 store、路由或后端接口）
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts src/components/dashboard/HeroMetrics.test.ts src/components/dashboard/TopicBoard.test.ts src/views/DashboardView.test.ts src/components/news/NewsCard.test.ts src/views/NewsFeedView.test.ts src/components/watchlist/WatchlistTable.test.ts src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/views/TopicDetailView.test.ts` 通过（10 个文件 / 21 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前高频业务页面已基本统一到同一视觉代际，但 `XMonitor`、`LlmSettings`、`Notify` 等功能页仍保留相对旧的层级和控件表达；如果后续继续深挖统一性，建议最后一轮再回到公共控件和功能页做 token / density 清理

## 2026-03-22 21:16

- 修改人：Codex
- 修改范围：`Dashboard` 与 `News Feed` 中间态终端视觉收敛
- 变更内容：继续沿用已确认的“冷蓝底 + 橙色焦点”中间态方向，对首页和新闻流进行第二、三阶段收敛。`Dashboard` 侧重把页面顶部明确为 `Control Room`，收紧指标卡为更硬的模块壳层、给主题卡增加更技术化的头部层级，并把右侧异动列进一步压成窄信号栏；`News Feed` 则把主区块升级为更像控制台的 `Control Station`，收紧过滤条边框与背景层次，并将统一新闻卡改成更紧凑的终端式外壳和微标签层级。整个过程只调整展示层与测试锚点，不改现有数据加载、排序、详情跳转或路由结构。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-22-dashboard-terminal-midstate-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-22-dashboard-terminal-midstate-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-22-news-feed-terminal-midstate-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-22-news-feed-terminal-midstate-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅前端展示层与测试断言调整，未改动 store、API client、路由契约或后端接口）
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts src/components/dashboard/HeroMetrics.test.ts src/components/dashboard/TopicBoard.test.ts src/views/DashboardView.test.ts src/components/news/NewsCard.test.ts src/views/NewsFeedView.test.ts` 通过（6 个文件 / 16 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前已完成壳层、首页和新闻流的中间态收敛，但 `Watchlist`、`WatchlistDetail`、`TopicDetail` 等页面仍停留在旧一档的克制冷蓝风格；如果后续要做全站统一，需要继续把同样的微标签层级、边框硬度和橙色焦点约束向这些页面扩展

## 2026-03-22 21:10

- 修改人：Codex
- 修改范围：`AppShell` 中间态终端壳层收敛
- 变更内容：按已确认的 Stitch 视觉提炼方向，收紧共享壳层的终端控制列表现：侧栏改为更硬的冷蓝基底与橙色焦点激活态，保留原有路由与序号模块结构；顶部新增全局细状态条，用于统一展示 `SSE` 状态、连接细节、最近事件时间与工作区标识；底部 `System Status` 模块同步收敛为更紧凑的系统信息卡，并将 `Desk` 说明改为更短的英文微标签 `Desk / News / Topics / Movers`；同时更新 `AppShell` 组件测试，锁定新状态条、文案和激活导航信号。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-22-app-shell-terminal-refinement-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅共享壳层展示层和测试断言调整，未改动路由、store 或 SSE 逻辑）
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前只完成共享壳层的中间态收敛，`Dashboard` 仍保留此前较克制的冷蓝风格；后续进入 `Dashboard` 时需要延续“橙色只做焦点，不做全局主色”的约束，避免整站过度交易终端化

## 2026-03-22 20:50

- 修改人：Codex
- 修改范围：`App Shell` 终端化视觉收敛设计文档
- 变更内容：结合用户确认的 Stitch 视觉提炼方向，新增 `App Shell` 视觉收敛设计文档，明确本轮只调整壳层视觉语言、不改路由和数据行为；设计确定采用“冷蓝底 + 橙色焦点”的中间态，重点收敛侧栏控制列、全局细状态条、导航激活信号和系统微标签层级，为后续按 `AppShell -> Dashboard -> News Feed` 顺序实施提供依据。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-22-app-shell-terminal-refinement-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅新增设计文档，未改动前后端代码或契约）
- 验证情况：文档变更，未执行代码测试
- 风险/后续事项：当前仅完成设计固化，尚未进入实现；下一步需要生成正式 implementation plan，并在实现时控制橙色焦点使用范围，避免壳层过度“交易终端化”

## 2026-03-21 22:50

- 修改人：Codex
- 修改范围：侧栏 `SYSTEM DESK` 说明区弱化
- 变更内容：将左侧边栏顶部原本较显眼的 `SYSTEM DESK` 标题和整句说明，收敛成一枚低调的 `Desk` 小标签加一行短说明 `新闻 / 主题 / 异动 / 流状态`，减少系统说明文案对主导航和内容区域的视觉干扰，同时保持终端式环境感；同步补充 `AppShell` 视图测试，锁定新的轻量标签和短说明文案。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前只弱化了侧栏头部说明区，导航标签和底部 `System Status` 卡仍保留较明确的系统语义；如果后续想继续统一“低调调试态”风格，可以再逐步收敛这些区域的术语和层级

## 2026-03-21 21:58

- 修改人：Codex
- 修改范围：Dashboard 顶部系统状态提示弱化
- 变更内容：将 Dashboard 顶部原先占用较大的 `StatusBanner` 横幅移除，改为标题区旁边的轻量状态 badge，仅用小圆点和短文案提示当前处于 `在线 / 降级 / 离线 / 连接中` 哪种调试状态，并附上简短辅助标识如 `SSE live`、`mock`、`SSE off`；颜色使用低饱和的绿、黄、红区分状态，避免“当前处于降级或断线状态”这类完整句子过于抢眼，同时不改变任何底层连接状态逻辑。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前只弱化了 Dashboard 顶部状态提示，其它页面如果仍使用 `StatusBanner` 仍会保持原先较显眼的横幅样式；如果你后续希望全站统一成低调状态 badge，需要再单独收敛公共状态组件策略

## 2026-03-21 21:52

- 修改人：Codex
- 修改范围：Dashboard 主列比例与异动侧栏收紧
- 变更内容：按用户要求进一步调整 Dashboard 桌面端三列权重，将 `News Feed / 资讯主题聚合 / 自选股异动` 的比例改为更明显的主次结构，使左侧 `News Feed` 成为主列；同时将右侧异动列进一步压缩成较窄侧栏，把默认预览项从 3 条缩到 2 条，并弱化单条异动的辅信息，只保留更紧凑的名称、代码和异动原因展示；同步更新视图测试，锁定新的三列比例类名、异动列标识和预览条目数量。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前右侧异动列已经明显收窄，如果后续再继续压缩，可能需要把顶部摘要面板也简化为更短的单行统计，避免头部信息占比过高

## 2026-03-21 20:32

- 修改人：Codex
- 修改范围：Dashboard 三列高密度布局重排
- 变更内容：将 Dashboard 从原先“上方主题/异动 + 下方最新新闻”的两段式结构改为桌面端三列并排看板，按 `自选股异动 / 资讯主题聚合 / News Feed` 三列排列并为每列加入独立滚动区，避免主题列表过长把最新新闻整体挤到首屏之外；同时压缩异动预览行、主题卡密度和 Dashboard 内的新闻条目形态，把 News Feed 改为更紧凑的标题优先列表；补充 Dashboard 视图测试，锁定三列结构标识、三列独立滚动容器和紧凑新闻预览项；同步新增本轮设计文档与实现计划。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-21-dashboard-three-column-density-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-21-dashboard-three-column-density-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅 Dashboard 视图结构和前端展示密度调整）
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前三列独立滚动只在桌面端开启，采用基于视口高度的上限策略；如果后续发现某些低高度屏幕首屏仍显压迫，可继续微调列高计算和主题列卡片密度

## 2026-03-21 21:02

- 修改人：Codex
- 修改范围：Dashboard 三列顺序调整
- 变更内容：按用户要求只交换桌面端三列中 `News Feed` 与 `自选股异动` 的位置，将桌面顺序从 `自选股异动 / 资讯主题聚合 / News Feed` 调整为 `News Feed / 资讯主题聚合 / 自选股异动`；移动端单列堆叠顺序保持不变；同时更新视图测试，显式锁定三列 DOM 顺序，避免后续回归。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次只调整桌面端列顺序，没有改变列宽比例；如果你后续觉得左侧 News Feed 视觉权重还不够，可以再继续微调三列宽度分配

## 2026-03-21 16:33

- 修改人：Codex
- 修改范围：`newsStore` 新闻列表状态分槽重构
- 变更内容：将原本共享一份 `items/activeQuery` 的 `newsStore` 改为“共享详情缓存 + 分离列表槽位”的结构，新增 Dashboard、News Feed、Sentiment News 三套独立的列表、查询、加载状态和时间戳，并分别提供 `loadDashboardNews`、`loadFeedNews`、`loadSentimentNews`、`refreshDashboardNews`；`AppShell` 启动改为只引导 Dashboard 槽位，`DashboardView`、`NewsFeedView`、`SentimentNewsView` 各自切换到自己的列表状态读取，彻底消除情绪页或筛选页覆盖首页统计和通用新闻流的问题；同时新增 `newsStore` store 级测试，并调整相关页面/壳层测试覆盖新的 store API。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/SentimentNewsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/SentimentNewsView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-21-news-store-list-scope-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-21-news-store-list-scope-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅前端 store 内部状态模型和消费方式调整）
- 验证情况：`npm --prefix frontend run test -- --run src/stores/newsStore.test.ts src/components/layout/AppShell.test.ts src/views/DashboardView.test.ts src/views/NewsFeedView.test.ts src/views/SentimentNewsView.test.ts` 通过（5 个文件 / 10 个用例）；`npm --prefix frontend run test -- --run` 通过（23 个文件 / 54 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前列表状态已按页面分槽，但详情和分析缓存仍是全局共享，这是本轮有意保留的复用层；如果后续新闻入口继续增加，可以沿用同样的槽位模式，或进一步抽象成通用 scoped list helper 以减少 store 字段重复

## 2026-03-21 16:26

- 修改人：Codex
- 修改范围：Dashboard 从情绪新闻页返回后的统计恢复
- 变更内容：修复从 `偏利好` / `偏利空` 情绪新闻页返回 Dashboard 后，首页统计仍停留在过滤结果的问题；根因是情绪新闻页会复用全局 `newsStore.items` 和 `activeQuery`，而 Dashboard 之前直接消费当前 store 数据，没有在挂载时恢复全量新闻流。现已在 Dashboard 挂载时检测当前新闻查询是否带筛选条件，若是则重新加载全量新闻，避免首页指标卡和“最新新闻”区域继续显示情绪过滤后的残留数据；同时补充前端回归测试覆盖这一返回场景。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run test -- --run` 通过（22 个文件 / 52 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前修复是让 Dashboard 进入时主动恢复全量新闻，能解决首页残留问题；但情绪页与通用新闻流仍共享同一个 `newsStore.items`，如果后续再增加更多专题化新闻入口，最好把不同新闻列表拆成独立 store 切片或本地列表状态，减少跨页面状态串扰

## 2026-03-21 16:01

- 修改人：Codex
- 修改范围：Dashboard 情绪指标卡入口与情绪新闻列表页
- 变更内容：将 Dashboard 上的 `偏利好` / `偏利空` 指标卡从静态计数改为可点击入口，分别跳转到新增的专用情绪新闻列表页；新增 `SentimentNewsView`，按对应情绪加载新闻并按时间倒序展示规整卡片，每条卡片展示标题、来源、时间、摘要和提及标的，点击后继续进入现有新闻详情页；同步补充 Dashboard/HeroMetrics/情绪新闻页的前端测试，以及本轮设计文档与实现计划。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/SentimentNewsView.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/SentimentNewsView.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-21-sentiment-news-entry-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-21-sentiment-news-entry-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅前端路由、页面交互和展示结构调整）
- 验证情况：`npm --prefix frontend run test -- --run src/components/dashboard/HeroMetrics.test.ts src/views/DashboardView.test.ts src/views/SentimentNewsView.test.ts` 通过（3 个文件 / 6 个用例）；`npm --prefix frontend run test -- --run` 通过（22 个文件 / 51 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前情绪新闻页仍复用 `newsStore.items` 作为列表缓存，进入该页会覆盖通用新闻流缓存；若后续要支持更重的情绪专题浏览，可能需要独立 store 切片或分页/批量详情接口来降低额外详情加载成本

## 2026-03-19 23:14

- 修改人：Codex
- 修改范围：Tailwind 迁移 code review 修正
- 变更内容：根据子代理代码审查修复了 3 个样式迁移回归：`WatchlistDetailView` 的涨跌额/涨跌幅现在直接使用 Tailwind 的 `text-positive` / `text-negative`，恢复单股行情正负反馈颜色；`XMonitorView` 的监控帖子流恢复为仅在桌面宽度下启用固定高度内部滚动，窄屏时回退为自然页面滚动，避免双滚动；`DashboardView` 的异动摘要卡片从无效的多层 `bg-[...]` 写法改为 `background-image` 渐变表达，恢复原先的摘要面板质感；并补充 `WatchlistDetailView` 对跌涨颜色语义的测试断言。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅 code review 修正）
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts src/views/XMonitorView.test.ts src/views/DashboardView.test.ts` 通过（3 个文件 / 7 个用例）；`npm --prefix frontend run test -- --run` 通过（21 个文件 / 48 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮 code review 中发现的问题已修复，但这类纯样式迁移仍主要依赖结构测试和人工页面巡检；如果下一轮继续压缩兼容层，建议补充至少一套截图级校验或手工核对清单

## 2026-03-19 22:56

- 修改人：Codex
- 修改范围：Tailwind 迁移剩余页面收尾与前端全量验证
- 变更内容：完成 `TopicDetailView`、`NewsDetailView`、`XMonitorView`、`LlmSettingsView`、`NotifySettingsView` 的 Tailwind 迁移，移除这些页面原有的 scoped CSS；为 `TopicDetail` 与 `Notify Settings` 新增页面级测试，为 `NewsDetail`、`XMonitor`、`LlmSettings` 补充稳定的结构锚点测试，确保主题来源导航、X 帖子翻译、LLM 设置页连接测试按钮和通知设置页测试消息按钮在重构后仍正常工作；至此本轮计划范围内的前端主页面都已迁到 Tailwind，且未改动任何前后端 API 契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NotifySettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NotifySettingsView.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅前端页面样式与测试补强）
- 验证情况：`npm --prefix frontend run test -- --run src/views/TopicDetailView.test.ts src/views/NewsDetailView.test.ts src/views/XMonitorView.test.ts src/views/LlmSettingsView.test.ts src/views/NotifySettingsView.test.ts` 通过（5 个文件 / 14 个用例）；`npm --prefix frontend run test -- --run` 通过（21 个文件 / 48 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前主页面已完成 Tailwind 迁移，但仓库里仍有部分子组件和兼容语义类（如 `surface`、`pill`）保留在全局样式中作为过渡层；如果下一轮要进一步收紧样式体系，应先确认这些兼容类在所有消费者中都已被完全替换后再清理

## 2026-03-19 22:43

- 修改人：Codex
- 修改范围：`NewsFeed`、`Watchlist`、`WatchlistDetail` 页面 Tailwind 迁移
- 变更内容：将 `NewsFeedView`、`WatchlistView` 和 `WatchlistDetailView` 迁移为 Tailwind class 驱动实现，移除对应页面的 scoped CSS；为新闻页壳层、自选股主布局、单股详情主网格补充稳定的 `data-role` 结构锚点，保持现有筛选、候选联想、关联新闻、详情卡片与单股行情展示行为不变；本轮仍只调整前端页面表现，没有改动 store 契约、API client 或任何后端接口。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅页面展示层重构）
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts` 通过（3 个文件 / 3 个用例）；`npm --prefix frontend run test -- --run` 通过（19 个文件 / 46 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 `TopicDetail`、`NewsDetail`、`XMonitor`、`LlmSettings`、`Notify` 等页面仍保留旧样式结构；继续迁移时要特别注意表单页和高密度数据页的交互状态，不要因 class 收敛误伤可读性或可点击区域

## 2026-03-19 22:29

- 修改人：Codex
- 修改范围：`Dashboard` 视图与仪表组件 Tailwind 迁移
- 变更内容：将 `HeroMetrics`、`TopicBoard` 和 `DashboardView` 迁移为 Tailwind class 驱动实现，去掉原有 scoped CSS；为指标区、主题卡片和 Dashboard 主网格补充稳定的 `data-role` 结构锚点，并给 `TopicBoard` 增加点击跳转的保护测试，确保后续继续重构页面时不会误伤导航与信息结构；本轮仍然只动前端展示层，没有改动任何前后端接口、store 读写或 API client 调用。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/HeroMetrics.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅 Dashboard 展示层与测试锚点调整）
- 验证情况：`npm --prefix frontend run test -- --run src/components/dashboard/HeroMetrics.test.ts src/components/dashboard/TopicBoard.test.ts src/views/DashboardView.test.ts` 通过（3 个文件 / 5 个用例）；`npm --prefix frontend run test -- --run` 通过（19 个文件 / 46 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前仅 `Dashboard` 完成页面级迁移，其余业务页面仍保留大量 scoped CSS；后续继续迁移时要优先复用已沉淀的 `SectionCard`、`StatusBanner` 和指标/卡片表达，避免不同页面重新各写一套 Tailwind 组合

## 2026-03-19 21:16

- 修改人：Codex
- 修改范围：前端共享组件 Tailwind 迁移第一批
- 变更内容：将 `SectionCard`、`StatusBanner`、`LoadingBlock`、`StaleBadge` 四个共享显示组件迁移为 Tailwind class 驱动实现，移除对应 scoped CSS；为 `SectionCard` 补充紧凑模式稳定标记 `data-compact`，并为 `SectionCard`/`StatusBanner` 增补 slot 与语义断言测试，确保后续页面迁移时仍有稳定的公共视觉锚点；本轮仅调整组件展示层，没有改动任何 store、API client 或后端接口。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/SectionCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/SectionCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/StatusBanner.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/StatusBanner.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/LoadingBlock.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/StaleBadge.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅共享展示组件样式层重构）
- 验证情况：`npm --prefix frontend run test -- --run src/components/common/SectionCard.test.ts src/components/common/StatusBanner.test.ts` 通过（2 个文件 / 4 个用例）；`npm --prefix frontend run test -- --run` 通过（19 个文件 / 44 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前只迁移了公共壳层和 4 个通用组件，页面级 scoped CSS 仍大量存在；后续迁移页面时需要尽量复用本轮沉淀的公共样式表达，避免模板 class 再次发散

## 2026-03-19 21:13

- 修改人：Codex
- 修改范围：前端 Tailwind 基础设施接入与 `AppShell` 首批迁移
- 变更内容：在前端引入 `tailwindcss@3`、`postcss` 与 `autoprefixer`，新增 Tailwind/PostCSS 配置并把现有全局 design tokens 映射进 Tailwind theme；`frontend/src/assets/main.css` 现改为 Tailwind 入口，同时保留当前暗色终端配色、`surface`、`pill` 等兼容语义类；`AppShell` 迁移为以 Tailwind class 驱动的布局和导航样式，不改动任何数据加载、SSE 连接或路由逻辑；同时补充 `AppShell` 的挂载/卸载测试，确认样式重构没有影响壳层数据初始化与断连清理。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/package.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/package-lock.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/tailwind.config.js`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/postcss.config.js`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/index.html`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/assets/main.css`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅前端样式基础设施与布局实现调整，未改动前后端 API 契约）
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run test -- --run` 通过（19 个文件 / 42 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前仅完成基础设施和 `AppShell`，其余页面仍混用现有 scoped CSS；Tailwind 迁移期内存在双样式系统，后续需要继续按计划逐页迁移并在完成后再清理兼容类

## 2026-03-19 21:01

- 修改人：Codex
- 修改范围：Tailwind 前端迁移方案设计文档与实施计划补强
- 变更内容：审查并重写了原有的 Tailwind 迁移计划，去掉“一次性完全替代手写 CSS”的大爆炸表述，改为“Tailwind 与现有 CSS 共存的渐进迁移”方案；新增正式设计文档，明确现有 design tokens 映射、迁移顺序、非目标、风险与验收方式；计划文档补充了按 `AppShell`、通用组件、Dashboard、其余页面、最终清理分块推进的任务结构，并加入更具体的测试与人工验收口径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-tailwind-migration-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-tailwind-migration-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅补充设计与计划文档）
- 验证情况：已人工核对当前前端技术栈、`frontend/src/assets/main.css` 现有 design token、`frontend/src/components/layout/AppShell.vue` 的布局结构，以及现有前端测试文件分布；未运行构建或测试命令，本次仅修改文档
- 风险/后续事项：本轮只补齐设计与计划，不包含实际 Tailwind 实现；若后续要正式开工，仍应按新设计/计划进入实施，并在每个迁移闭环完成后继续更新记录

## 2026-03-19 20:36

- 修改人：Codex
- 修改范围：LLM 设置页“测试连接”功能与上游鉴权错误透传
- 变更内容：在 `LLM Settings` 页面新增“测试连接”按钮，严格按已保存且当前激活的 LLM 配置发起连通性校验，不会读取未保存的表单草稿；后端新增 `POST /api/llm/test` 接口，并让 `OpenAICompatibleProvider` 在上游返回 4xx/5xx 时优先解析真实错误正文，避免只显示裸状态码；已通过直接请求 DeepSeek 官方接口确认当前真实失败根因为 API key 无效，上游返回 `Authentication Fails, Your api key: ****20e1 is invalid`，页面现在可直接展示这类错误。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/llm.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/llm.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_analysis.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/llmStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-llm-connection-test-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-llm-connection-test-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（新增 `POST /api/llm/test`；前端新增连接测试响应类型）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_analysis.py backend/tests/test_llm_config.py -q` 通过（18 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/views/LlmSettingsView.test.ts` 通过（2 个文件 / 11 个用例）；`npm --prefix frontend run build` 通过；使用本地保存的当前 key 直连 `https://api.deepseek.com/v1/chat/completions` 已确认真实返回 `401` 和错误正文 `Authentication Fails, Your api key: ****20e1 is invalid`
- 风险/后续事项：测试连接会真实消耗一次上游请求额度；当前失败不是代码兼容性问题，而是当前保存的 DeepSeek key 被上游判定无效，需要你换成有效 key 后再次保存并点击“测试连接”

## 2026-03-19 20:18

- 修改人：Codex
- 修改范围：LLM DeepSeek 默认配置持久化、错误域名修正与设置页真实错误态
- 变更内容：定位并修复了本地 LLM 设置“刷新后看起来被改回去”的根因：前端 `LLM Settings` 读取/保存配置时不再在后端失败后静默回退 `mockLlmConfig`，而是展示真实加载失败信息，避免 mock 假数据覆盖数据库中的真实 DeepSeek 配置；后端新增对已知错误 DeepSeek 域名 `https://api.deepssek.com/v1` 的规范化保存，自动改写为正确的 `https://api.deepseek.com/v1`；同时已直接修正本地 SQLite 中当前激活的 DeepSeek 配置，消除导致 `llm provider request failed: [SSL: UNEXPECTED_EOF_WHILE_READING] ...` 的错误地址。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/llm_provider_config_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_llm_config.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/llmStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/app.db`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-llm-deepseek-default-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-llm-deepseek-default-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅调整前端错误处理与后端保存时的 DeepSeek 域名规范化）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_llm_config.py -q` 通过（5 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/views/LlmSettingsView.test.ts` 通过（2 个文件 / 9 个用例）；`npm --prefix frontend run build` 通过；本地 SQLite 已核对当前激活配置为 `openai_compatible / DeepSeek / https://api.deepseek.com/v1 / deepseek-chat`
- 风险/后续事项：当前后端只会自动纠正已知的 DeepSeek 错拼 host，不会改写其它自定义 OpenAI-compatible 地址；如果后续仍有连接失败，需要继续检查 API key、本机网络或上游服务可用性

## 2026-03-19 19:40

- 修改人：Codex
- 修改范围：`X Monitor` provider 健康语义、空账号冷却行为、twitterapi.io 搜索 limit 和测试隔离修正
- 变更内容：根据推送前 code review 修正 `X Monitor` 的剩余语义缺口：`/api/health` 与 `/api/health/x` 现在都基于首个激活账号的 `last_tweets` 轻量探测判定 provider 状态，不再仅凭 API key 是否存在就标记健康；健康探测增加进程内缓存，避免健康轮询持续消耗 provider 配额；空账号/空配置文件时的 refresh 不再推进 3 小时冷却；`twitterapi.io` 的 `advanced_search` 现在会真正透传 `limit` 参数；同时为 `TwitterApiIoClient` 的进程级状态补上测试级自动重置，消除顺序依赖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/twitterapi_io_client.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_analysis.py backend/tests/test_x_monitor.py -q` 通过（26 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/views/XMonitorView.test.ts` 通过（2 个文件 / 9 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 provider 健康仍依赖首个激活账号的 `last_tweets` 可用性，如果后续账号名单里首个账号长期异常而其他账号正常，健康状态可能偏保守；如要进一步降低探测成本，可后续引入更明确的 provider 级健康缓存字段或专用轻量探测端点

## 2026-03-19 19:07

- 修改人：Codex
- 修改范围：LLM 翻译上游连接失败时的错误收敛
- 变更内容：定位到 `POST /api/llm/translate` 在上游模型地址不可达时会把 `httpx` 连接异常直接抛成 500，前端只能看到笼统失败；后端 `OpenAICompatibleProvider` 现已捕获 `httpx.HTTPError` 并统一转成 `LLMProviderError`，接口会返回明确的 `502 + detail`，便于直接判断是 `base_url`、SSL 还是网络连通性问题。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_analysis.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅改进错误返回）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_analysis.py -q -k 'translate or connection_errors'` 通过（5 个用例）；本地请求 `POST http://127.0.0.1:8000/api/llm/translate` 已返回明确错误详情 `llm provider request failed: [SSL: UNEXPECTED_EOF_WHILE_READING] ...`
- 风险/后续事项：当前真实失败仍然存在，根因是本地保存的 `base_url`/上游服务不正确或不可连；需要把 `LLM Settings` 里的 `base_url` 改成实际模型服务地址后再验证

## 2026-03-19 18:37

- 修改人：Codex
- 修改范围：`X Monitor` 帖子按需中文翻译、LLM 文本翻译接口与前端会话缓存
- 变更内容：后端新增 `POST /api/llm/translate`，复用当前激活的 LLM provider/model 对单条帖文正文做中文翻译，并增加空文本、超长文本和空翻译返回的校验；前端 `X Monitor` 监控列表和关键词搜索结果都新增 `翻译` 按钮、翻译中/失败/成功展示，以及基于稳定 `translationKey` 的页面内会话缓存，避免搜索结果 `id=0` 时出现串译；同时补充前端 API client 测试、视图测试，以及本轮设计/计划文档。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/llm.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/llm.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_analysis.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/http.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-x-monitor-translation-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-x-monitor-translation-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（新增 `POST /api/llm/translate`；前端新增翻译请求/响应类型）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_analysis.py -q` 通过（9 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/views/XMonitorView.test.ts` 通过（2 个文件 / 9 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前翻译缓存只保存在页面会话内，刷新后会失效；翻译接口对正文长度限制为 4000 字符，若后续要支持更长内容，需要按 provider 上下文窗口改成截断或分段策略

## 2026-03-19 17:40

- 修改人：Codex
- 修改范围：`X Monitor` 页面右侧帖子流密度与高度控制优化
- 变更内容：将 `X Monitor` 页面“账号监控帖子流”从大卡片纵向堆叠改为“状态式摘要 + 紧凑列表流”，摘要主句新增当前跟踪帖子数与同步状态提示，副句汇总请求节流、刷新冷却和最近刷新时间；帖子列表在桌面端改为固定最大高度并在面板内部滚动，单条帖子收敛为更小的列表项，减少页面纵向拉伸并提升同屏信息密度；同步补充本轮设计文档、实现计划和前端视图测试断言。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-x-monitor-feed-density-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-x-monitor-feed-density-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 2 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：摘要中的帖子数为当前前端筛选结果数量，不代表后端库中的全量帖子数；桌面端内部滚动高度使用响应式 `clamp`，若后续页面再加入更多头部内容，可能需要再微调高度上限

## 2026-03-19 18:27

- 修改人：Codex
- 修改范围：`X Monitor` 页面改为显示后端真实下发的节流/冷却配置，小号文案收敛
- 变更内容：扩展 `GET /api/health/x` 响应，新增 `min_interval_seconds` 和 `refresh_cooldown_hours`，前端 `X Monitor` 页面改为直接使用后端下发的真实配置值展示“请求节流”和“账号刷新冷却”，不再写死 `6 秒` 与 `3 小时`；同时将原先占位较大的策略说明块收敛为页面顶部的小号次级文案，减少视觉占用。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（`GET /api/health/x` 新增 `min_interval_seconds`、`refresh_cooldown_hours`）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q -k provider_state` 通过；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 2 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前页面已与后端配置值同步，但配置仍来自进程启动时读取的 `.env`；如果运行中手改 `.env` 而不重启后端，页面不会立即反映新值

## 2026-03-19 18:21

- 修改人：Codex
- 修改范围：`X Monitor` 页面展示 provider 节流与账号冷却策略
- 变更内容：在 `X Monitor` 页面“状态与筛选”卡片中新增两条明确的运行策略说明，展示当前 `twitterapi.io` provider 请求节流为 `6 秒/次`，账号刷新冷却为 `3 小时`，帮助页面直接解释为什么刷新会等待或跳过；同时补充视图测试覆盖这些说明文案。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 2 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前页面中的 `6 秒/次` 与 `3 小时` 为按当前后端配置写死的展示文案，若后续你调整 `.env` 中的节流参数而不改页面，展示值不会自动变化；如需完全与后端配置同步，下一步应把节流配置值加入健康接口

## 2026-03-19 18:08

- 修改人：Codex
- 修改范围：`twitterapi.io` 最小请求间隔节流、真实 `MiniMax_AI` provider 验证
- 变更内容：后端新增 `twitterapi_io_min_interval_seconds` 配置项，并在 `TwitterApiIoClient` 中加入进程内最小请求间隔节流；本地 `.env` 默认配置为 6 秒，确保真实 provider 请求严格按免费额度节奏发起。基于该节流对 `MiniMax_AI` 连续发起两次真实 `last_tweets` 请求，已拿到相同的真实帖子数据，且返回中的账号、链接、发布时间、正文均直接来自 provider 原始响应。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/twitterapi_io_client.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/.env`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-twitterapi-rate-limit-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-twitterapi-rate-limit-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（仅新增后端节流配置）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q -k min_interval` 通过；`conda run -n news-caught pytest backend/tests -q` 通过（60 个用例）；使用真实 key 对 `MiniMax_AI` 连续请求两次，得到同一条真实帖子：`https://x.com/MiniMax_AI/status/2034528945962696948`，发布时间 `Thu Mar 19 07:14:35 +0000 2026`，正文 `Early testers are saying that M2.7 has big improvements in emotional intelligence and character consistency 👀`
- 风险/后续事项：当前节流为单进程内最小间隔，若未来有多进程部署仍可能并发打到 provider；单个请求本身的网络耗时会占用部分 6 秒窗口，因此两次调用的总间隔是“请求耗时 + 必要补等待”

## 2026-03-19 18:03

- 修改人：Codex
- 修改范围：`twitterapi.io` 请求节流设计与实现计划文档
- 变更内容：新增 `twitterapi.io` 最小请求间隔的设计与计划文档，确定在后端增加可调节的 provider 请求节流配置，并按用户要求默认以 6 秒为最小真实请求间隔，对 `last_tweets` 和 `advanced_search` 统一生效。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-twitterapi-rate-limit-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-twitterapi-rate-limit-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（本次仅新增设计与计划文档）
- 验证情况：已人工核对当前 `TwitterApiIoClient` 请求路径和本地 `.env` 配置
- 风险/后续事项：本轮节流为进程内最小间隔，不处理多进程共享配额；真实联调仍取决于 provider 对当前 key 的即时限流状态

## 2026-03-19 17:10

- 修改人：Codex
- 修改范围：`X Monitor` 三小时刷新冷却、`MiniMax_AI` 单账号名单、前后端提示与验证
- 变更内容：为 `X Monitor` 账号刷新增加 3 小时硬冷却，后端新增 `x_monitor_refresh_cooldown_hours` 默认配置，并在 `POST /api/x/refresh` 响应中返回 `skipped`、`skip_reason` 和 `next_refresh_at`；当冷却窗口未过时，本地直接跳过刷新而不访问远端 provider。前端 `X Monitor` 页面新增“冷却中，下次可刷新”提示；样例账号名单改为仅保留 `MiniMax_AI`；链接仍只使用 `twitterapi.io` 返回的真实原帖 URL，不做拼接或伪造。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/x_monitor_accounts.example.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-x-monitor-refresh-cooldown-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-x-monitor-refresh-cooldown-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（`POST /api/x/refresh` 响应新增 `skipped`、`skip_reason`、`next_refresh_at`）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q` 通过（10 个用例）；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 2 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（59 个用例）；`npm --prefix frontend run build` 通过；使用真实 `TWITTERAPI_IO_API_KEY` 对 `MiniMax_AI` 做 smoke test 时，首次真实刷新仍命中 provider `429`，但在预置最近成功时间后再次调用已确认会直接返回 `skipped=true` 和 `cooldown_active`
- 风险/后续事项：当前 3 小时冷却能避免高频重复拉取，但不能解决 provider 在首次请求前就已对当前 key 限流的情况；如果后续 `MiniMax_AI` 仍需要更稳定的真实抓取，可能还要加失败后的退避窗口或改用更低频的自动调度

## 2026-03-19 17:06

- 修改人：Codex
- 修改范围：`X Monitor` 三小时冷却设计与实现计划文档
- 变更内容：新增 `X Monitor` 三小时刷新冷却的设计与计划文档，确定账号名单切为仅保留 `MiniMax_AI`，账号刷新改为每 3 小时最多执行一次，冷却期内直接跳过远端请求并返回下次可刷新时间，关键词搜索保持不变。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-x-monitor-refresh-cooldown-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-x-monitor-refresh-cooldown-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（本次仅新增设计与计划文档，代码实现尚未开始）
- 验证情况：已人工核对现有 `x_monitor` 刷新逻辑、健康记录模型和前端页面边界；真实联调中已确认需要对 `429` 做降频处理
- 风险/后续事项：后续实现需要确保冷却策略不会误伤关键词搜索；真实 smoke test 仍需以 `MiniMax_AI` 返回结果和当前 key 的限流表现为准

## 2026-03-19 16:33

- 修改人：Codex
- 修改范围：`X Monitor` provider 替换、桥接移除、前后端接口与页面、测试与文档
- 变更内容：将 `X Monitor` 从本地 `grok-bridge` 桥接方案改为直接使用 `twitterapi.io` API key；后端新增 `twitterapi_io_client`，重写 `x_monitor` 刷新逻辑以按账号拉取最新推文并按 tweet id 优先去重，新增 `GET /api/x/search` 关键词搜索接口，健康检查字段从 `bridge_* / x_bridge_*` 改为 `configured / healthy / status` 与 `x_monitor_*`；前端同步更新 `X Monitor` 页面、类型、mock 与 store，增加关键词搜索区并替换全部 `grok-bridge` 文案；README 与 API 契约文档改为 `twitterapi.io` 配置方式，并删除旧桥接客户端实现；联调阶段根据真实 `last_tweets` 响应修正为读取 `data.tweets`，并补充 X 风格 `createdAt` 时间解析。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/twitterapi_io_client.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/grok_bridge_client.py`（删除）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/.env`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/x_monitor_accounts.example.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/api-contract.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（新增 `GET /api/x/search`；`GET /api/health` 的 `x_bridge_*` 改为 `x_monitor_*`；`GET /api/health/x` 的 `bridge_*` 改为 `configured / healthy / status`）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q` 通过（9 个用例）；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 1 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（58 个用例）；`npm --prefix frontend run build` 通过；使用用户提供的真实 `TWITTERAPI_IO_API_KEY` 直连 `https://api.twitterapi.io/twitter/user/last_tweets?userName=DeItaone&includeReplies=false` 已拿到真实响应，并确认 `tweets` 位于 `data.tweets`；单账号 refresh smoke test 已跑通配置与 provider 健康检查，但连续请求命中 `429` 限流
- 风险/后续事项：当前 key 在短时间连续拉取多账号时会命中 `429`，因此实际使用中需要降低刷新频率、控制账号数量或后续改造成更适合多账号的监控模式；本轮默认账号列表已切成偏美股快讯方向，但是否保留这些账号仍取决于你的偏好

## 2026-03-19 16:26

- 修改人：Codex
- 修改范围：`twitterapi.io` 替换 `X Monitor` 桥接方案设计文档
- 变更内容：新增 `twitterapi.io` 替换现有 `grok-bridge` 型 `X Monitor` 的设计文档，明确第一版采用“账号监控轮询 + 关键词手动搜索”的双通道方案，保留现有 `X Monitor` 页面和大部分数据模型，完整移除桥接依赖，并规划新的配置项、健康检查语义、接口边界、测试策略和后续演进方向。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-19-twitterapi-io-x-monitor-replacement-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（本次仅新增设计文档，尚未进入实现）
- 验证情况：已人工核对设计文档与仓库现有 `X Monitor`、配置、健康检查和 README 中的桥接边界；参考了 `twitterapi.io` 官方文档中的账号最新推文、搜索推文和监控接口能力
- 风险/后续事项：设计已明确方向，但真实实现仍需以 `twitterapi.io` 实际响应结构为准；进入实现与联调阶段前，需由用户提供有效 API key 和目标账号列表

## 2026-03-19 16:39

- 修改人：Codex
- 修改范围：`twitterapi.io` 替换 `X Monitor` 的实现计划文档
- 变更内容：新增实现计划文档，按 TDD 顺序拆分了桥接测试替换、后端 provider 接入、健康检查字段调整、关键词搜索接口、前端 store 与页面改造、README 清理以及最终验证步骤，并明确真实联调需要用户提供 `TWITTERAPI_IO_API_KEY` 和账号列表。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-19-twitterapi-io-x-monitor-replacement-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无（本次仅新增实现计划文档，尚未进入代码实现）
- 验证情况：已人工核对计划文档中的文件边界与当前 `X Monitor` 后端测试、前端 store、API client 和类型定义
- 风险/后续事项：计划已覆盖实现顺序，但真实 provider 字段映射仍需在编码阶段以 `twitterapi.io` 响应为准；最终 smoke test 仍依赖用户提供真实 API key 与账号列表

## 2026-03-19 15:34

- 修改人：Codex
- 修改范围：X Monitor 本地启用配置、外部 `grok-bridge` 仓库落地
- 变更内容：将 `ythx-101/grok-bridge` 仓库克隆到本机 `/Users/xiuyang/projects/grok-bridge`，并在项目根目录新增本地 `.env`，启用 `X_MONITOR_ENABLED`、配置 `GROK_BRIDGE_BASE_URL`、超时时间和账号白名单文件路径，使当前仓库可按真实本地路径接入 `grok-bridge`。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.env`（新增，本地配置）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught python -c "from backend.app.core.config import get_settings; s=get_settings(); print(s.x_monitor_enabled); print(s.grok_bridge_base_url); print(s.x_monitor_accounts_file)"` 输出已确认读取到新增配置；`python3 /Users/xiuyang/projects/grok-bridge/scripts/grok_bridge.py --help` 可运行
- 风险/后续事项：`X Monitor` 仍依赖 Safari 已登录 `grok.com` 且开启 “Allow JavaScript from Apple Events”；如果未满足该前置条件，`/api/health/x` 会显示桥接异常，但不影响当前 `.env` 配置已生效

## 2026-03-19 11:20

- 修改人：Codex
- 修改范围：新闻 refresh 后自动情绪标注与主题聚合增量流水线、后端测试、设计与计划文档
- 变更内容：新增 `NewsSignalPipelineService`、规则情绪分类器和信号结果持久化，在每次 `POST /api/news/refresh` 成功插入新闻后自动对增量新闻生成 `sentiment_label` / `sentiment_score`、归并到 `topic_cluster` 并写入 `topic_news_link`；当本次 refresh 没有新增新闻时，会顺手回填一批历史 `signal_status is null` 的新闻，避免库里已有未打标新闻长期不被处理；新增 `news_item` 信号状态字段、`topic_cluster` 归并字段和 `news_signal_result` 表，并补充增量分类/聚合/降级/refresh 触发的后端测试及本轮设计、计划文档。
- 影响文件：
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/db/initializer.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/models/__init__.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/models/news_item.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/models/news_signal_result.py`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/models/topic_cluster.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/repositories/news_signal_repository.py`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/services/news_signal_classifier.py`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/app/services/news_signal_pipeline.py`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/backend/tests/test_news_signal_pipeline.py`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/docs/superpowers/specs/2026-03-19-auto-signal-topic-pipeline-design.md`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/docs/superpowers/plans/2026-03-19-auto-signal-topic-pipeline-plan.md`（新增）
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex-auto-signal-topic/docs/code-change-log.md`
- 接口/数据结构变化：有（`news_item` 新增 `signal_status`、`signal_error`、`signal_updated_at`；`topic_cluster` 新增 `topic_key`、`cluster_version`、`llm_refined_at`；新增 `news_signal_result` 表，但现有 API 契约保持兼容）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py backend/tests/test_news_ingestion.py -q` 通过（13 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（55 个用例）
- 风险/后续事项：当前主题聚合仍以规则 token/topic key 为主，适合先把空值和无聚合问题补齐，但复杂跨语种话题的命名质量仍取决于后续启用 `ai_enabled` 后的 LLM 提炼；SQLite 现有库通过启动时补列兼容升级，若后续要上更严格索引或唯一约束，建议引入正式 migration

## 2026-03-18 21:35

- 修改人：Codex
- 修改范围：Dashboard 自选股异动面板摘要化、前端视图测试、设计与计划文档
- 变更内容：将 Dashboard 页原先按 `abnormalMovers` 全量纵向铺开的 `Live Movers` 列表改为“顶部摘要 + 3 条代表项 + 查看全部入口”的压缩结构；新增本地市场分布和主异动原因聚合文案，避免异动股票过多时把总览页拉成长列表，同时保留跳转到 Watchlist 查看完整异动的入口；同步补充该轮设计文档、实现计划和页面测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-dashboard-movers-summary-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-dashboard-movers-summary-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 1 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前“主因”文案来自前端对 `abnormal_reason` 的有限映射，后端若新增原因类型会先回退显示原始值；代表项顺序继续沿用 `abnormalMovers` 当前顺序，如果后端排序策略改变，Dashboard 预览顺位也会随之变化

## 2026-03-18 20:38

- 修改人：Codex
- 修改范围：自选股页搜索候选添加、删除能力、后端候选/删除接口、前端测试与设计计划文档
- 变更内容：将自选股页原先左侧手填 `symbol + display_name` 的添加表单改为“表格上方搜索添加栏 + 候选下拉”的一体化管理面板；新增内置股票候选库和 `GET /api/watchlist/candidates` 接口，前端支持按代码、中文名、英文名和别名做本地模糊匹配，选中候选后直接添加，不再要求手工录入代码与名称；新增 `DELETE /api/watchlist/{symbol}` 接口和表格行内删除按钮，删除前使用确认框并避免按钮点击误触发行跳转；同步扩展前端 mock、store 状态和回归测试，并补充本轮设计文档和实现计划。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/watchlist.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/watchlist_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/watchlist.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/watchlist_candidates.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stock_news_search.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/http.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.test.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/vitest.config.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-watchlist-search-delete-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-watchlist-search-delete-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（新增 `GET /api/watchlist/candidates`、`DELETE /api/watchlist/{symbol}`；前端新增 `WatchlistCandidate` 数据结构）
- 验证情况：`conda run -n news-caught pytest backend/tests/test_stock_news_search.py -q` 通过（10 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts src/components/watchlist/WatchlistTable.test.ts` 通过（3 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前候选库是内置静态清单，覆盖范围取决于维护的数据；如果后续要支持更多港股/美股，需要继续补充候选源或改成服务端查询；删除 watchlist 仅移除 watchlist 项，不会清理历史行情快照或关联新闻数据，这是本轮刻意保留的数据独立性策略

## 2026-03-18 16:45

- 修改人：Cursor
- 修改范围：自选股添加时自动关联新闻（DB 匹配 + Tavily + Google News RSS + LLM 可选增强）
- 变更内容：添加自选股时自动搜索并关联最新相关新闻。同步阶段用 symbol 和 display_name 在现有 `news_item` 表中做关键词匹配并写入 `news_stock_mention`；阈值判断基于实际命中的新闻条数，低于阈值（默认 3）时启动后台线程依次尝试 Tavily Search API（需配置 `tavily_api_key`）和 Google News RSS（免费兜底）搜索外部新闻入库；如果 LLM 已配置，会在外部搜索前用 LLM 扩展搜索关键词（公司别名、中文名等），LLM 未配置时优雅降级为规则关键词。新增 `TavilyClient`、`GoogleNewsSearchClient`、`StockNewsSearchService` 三个服务，修改 `POST /api/watchlist` 集成自动关联逻辑，新增 `tavily_api_key` 和 `stock_news_min_count` 配置项。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/tavily_client.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/google_news_search.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/stock_news_search.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/watchlist.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stock_news_search.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-watchlist-auto-news-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有（`POST /api/watchlist` 行为变更：添加后自动关联新闻；Settings 新增 `tavily_api_key`、`stock_news_min_count`）
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（47 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：Tavily API 有免费额度限制（1000 次/月），超限后自动降级到 Google News RSS；Google News RSS 被 Google 限流时搜索会静默失败；LLM 关键词扩展依赖已配置的 LLM provider，未配置时跳过；后台线程异常不影响主请求，但搜索结果会延迟出现；前端无需修改，`news_stock_mention` 数据补齐后关联新闻自动展示

## 2026-03-18 16:12

- 修改人：Codex
- 修改范围：飞书通知回归修复、后端回归测试、前端 mock 回归测试、设计与计划文档
- 变更内容：修复飞书通知两个合并阻塞回归：新闻刷新接口不再通过“最近 N 条”反推新增新闻，而是由 `NewsIngestionService` 显式返回本次真实插入的 `inserted_items` 供通知使用；自选股异动通知改为进程内边沿触发状态机，只有首次越过阈值时发送，跌回阈值内后才允许下一次再次提醒，避免页面启动和 watchlist 读取重复刷屏；同时修正前端 mock 降级下飞书配置保存逻辑，编辑已配置项且留空 `app_secret` 时继续保留 `app_secret_set=true`。补充后端新闻刷新/自选股通知回归测试和前端 API client 回归测试，并新增本轮设计、计划文档。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/notification_service.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-feishu-notification-bugfix-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-feishu-notification-bugfix-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无对外 API 结构变化；内部 `RefreshSummary` / `SourceFetchResult` 新增 `inserted_items` 字段用于通知链路
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_market.py backend/tests/test_feishu_notify.py -q` 通过（20 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts` 通过（1 个文件 / 1 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：自选股提醒状态仍是进程内内存，服务重启后若股票仍处于阈值外，首次读取 watchlist 仍会补发一次；本轮未把提醒迁到独立调度任务，后续若要彻底去除读接口副作用，建议再拆为后台轮询

## 2026-03-18 14:30

- 修改人：Cursor
- 修改范围：飞书应用 Bot 推送通知全链路、前后端配置管理、业务集成、测试与设计文档
- 变更内容：新增飞书应用 Bot API 推送通知功能，支持三类信号推送（新闻聚合、自选股异动、LLM 分析结果）；后端新增 `FeishuNotifyConfig` 模型、仓储、Schema、`FeishuClient` 飞书 API 客户端（tenant_access_token 鉴权 + 消息卡片发送）、`NotificationService` 通知服务（进程内事件缓冲 + 定时聚合推送 + 实时推送）、`/api/notify/feishu/*` 配置与测试接口；将通知集成到新闻刷新（news.refresh）、LLM 分析（news.analyze）和自选股行情（market.watchlist）三个业务入口；前端新增通知设置页 `/settings/notify`（飞书凭证、目标类型、通知开关、聚合间隔、测试按钮）、`notifyStore`、API client 扩展和 mock 降级；侧栏导航新增 `06 Notify` 入口。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/feishu_notify_config.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/feishu_notify_config_repository.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/feishu_notify.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/feishu_client.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/notification_service.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/notify.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/router.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_feishu_notify.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/notifyStore.ts`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NotifySettingsView.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-feishu-notification-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（38 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：飞书凭证（App ID/App Secret）存储在数据库明文，与 LLM key 同级安全策略，适合个人使用；新闻聚合使用进程内定时器，服务重启后缓冲区清空；自选股异动检测挂在行情查询入口，仅在行情被请求时触发，后续可加独立定时轮询；关键词过滤为子串匹配，后续可升级为分词匹配

## 2026-03-18 13:06

- 修改人：Codex
- 修改范围：自选股详情页指标卡与关联新闻卡终端化、测试、设计与计划文档
- 变更内容：把自选股详情页 `指标详情` 区块中仍然发灰发亮的小卡片，以及 `关联新闻` 区块中仍然偏亮的新闻卡统一切换为深色终端表面，补齐终端卡钩子、文字对比度和 hover 层级，使该页面与前面已经收紧的终端视觉体系保持一致。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-watchlist-detail-terminal-polish-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-watchlist-detail-terminal-polish-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts` 通过（1 个文件 / 1 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts src/views/LlmSettingsView.test.ts src/components/watchlist/WatchlistTable.test.ts` 通过（3 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮只修正自选股详情页卡片表面和文字层级，不调整布局与数据逻辑；如果后续仍觉得信息块太平，可以再给数值卡加入更精细的数值权重和边界光效

## 2026-03-18 12:35

- 修改人：Codex
- 修改范围：终端交互态细化、共享状态组件与导航交互、验证
- 变更内容：在高对比终端视觉基础上继续统一 `hover / focus / selected / disabled` 交互反馈，为全局 token 增加交互态色值与 focus ring；细化 AppShell 导航 hover、StatusBanner tone 层级、自选股表格选中态、Topic/Watchlist/X Monitor/Topic Detail/News Detail/LLM Settings 等页面中的卡片 hover、按钮 hover 与 disabled 态，使页面更接近交易终端的反馈节奏，而不再停留在“深色静态页面”。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/assets/main.css`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/StatusBanner.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts src/views/NewsFeedView.test.ts src/components/news/NewsCard.test.ts` 通过（5 个文件 / 6 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮主要增强交互态一致性，没有改变布局或数据逻辑；如果后续还要进一步提升终端沉浸感，建议补全更多页面的 disabled / empty / loading 态视觉标准，而不是继续单点修补

## 2026-03-18 12:28

- 修改人：Codex
- 修改范围：LLM Settings 页面表单终端化、测试、设计与计划文档
- 变更内容：将 `LLM Settings` 页中仍然使用白色底板的输入框全部切换为深色终端输入面板，补齐字段终端钩子、placeholder 对比度、focus 态描边、按钮渐变和成功/失败提示色，避免该页面继续出现刺眼白底破坏整体科技终端风格；同时新增本轮设计与计划文档并扩展页面测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/LlmSettingsView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-llm-settings-terminal-input-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-llm-settings-terminal-input-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts` 通过（1 个文件 / 2 个用例）；`npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts` 通过（3 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮只修正了 `LLM Settings` 表单视觉，不改变保存逻辑；如果后续还要继续增强科技感，可再统一所有表单页面的 hover / disabled / invalid 态

## 2026-03-18 12:22

- 修改人：Codex
- 修改范围：前端高对比终端视觉修复、仓库级 visual companion 启动脚本、测试与设计/计划文档
- 变更内容：将多个仍使用浅灰白半透明表面的区域统一收敛回深色终端表面，重点修复自选股表格、Dashboard 主题卡、Watchlist 关联新闻卡、X Monitor 指标卡与筛选框、Topic Detail 过滤区和来源卡、News Detail 分析卡的低对比度问题，并同步提亮次级文字和链接/按钮高亮，强化科技终端感；同时新增仓库级 `scripts/start-server.sh` 包装脚本，转发到 `brainstorming` skill 中真实存在的启动脚本，避免后续在仓库根目录直接执行时报“文件不存在”。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/assets/main.css`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/SectionCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/dashboard/TopicBoard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/scripts/start-server.sh`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-terminal-contrast-polish-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-terminal-contrast-polish-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts` 通过（2 个文件 / 2 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts src/views/NewsFeedView.test.ts src/components/news/NewsCard.test.ts` 通过（4 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮主要通过统一深色表面和提高文字对比度来修复可读性，属于视觉收敛而非结构重做；如果后续要继续细化“科技感”，下一步适合补更系统的 hover / focus / row-selected 态，而不是再引入浅色大面积底板

## 2026-03-18 11:45

- 修改人：Codex
- 修改范围：News Feed 首页信息编排、统一横向新闻卡、前端测试、设计与计划文档
- 变更内容：取消首页 `Primary Signal` 与 `Signal Queue` 的 editorial 分层，不再按重要度放大或重排新闻，改为直接按当前数据顺序渲染统一的 `News Stream` 横向卡片列表；同时将首页新闻卡统一为横向信息结构，左侧显示标题与摘要，右侧显示时间与主题，避免中间三张卡继续呈现竖向高卡；删除已不再使用的 `LeadStoryCard` 组件及其测试，避免把被废弃的首页主卡方案继续留在可执行代码里；补充对应设计文档、实现计划与前端测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-news-feed-unified-horizontal-list-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-news-feed-unified-horizontal-list-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/news/NewsCard.test.ts src/components/news/StoryStrip.test.ts` 通过（3 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮按需求明确取消了首页的“主信号推荐”层次，如果后续仍需要突出某类新闻，建议通过可切换排序或单独筛选实现，而不是重新引入放大型主卡

## 2026-03-18 11:28

- 修改人：Codex
- 修改范围：News Feed 首页冷蓝灰终端配色、Primary Signal 主卡布局、前端测试、设计与计划文档
- 变更内容：将首页全局终端色板从偏亮橙蓝辉光收敛为冷蓝灰交易终端风，压暗背景和表面层级并将高亮统一为少量青色信号；把 `Primary Signal` 主卡从纵向海报式超大标题改为更紧凑的终端主卡，采用顶部信号标签、中部压缩标题与 2 到 3 行摘要、底部横向 meta 信息带的结构；同时新增 `LeadStoryCard` 测试覆盖新结构钩子，并补充本轮设计文档和实现计划。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/assets/main.css`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-18-news-feed-terminal-refinement-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-18-news-feed-terminal-refinement-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/news/LeadStoryCard.test.ts src/views/NewsFeedView.test.ts` 通过（2 个文件 / 2 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮主要压缩了首页主卡和终端色板，其他页面仍沿用同一 token 体系但未逐页做更细的视觉平衡检查；若后续需要继续增强“交易终端”气质，可再细调卡片密度和导航区信息层级

## 2026-03-18 01:43

- 修改人：Codex
- 修改范围：前端全局终端式视觉系统、AppShell、共享组件、News Feed、Dashboard、前端测试
- 变更内容：将前端主视觉从暖色杂志风切换为冷色金融终端风，重写全局 design tokens、焦点态和语义色；重做 `AppShell` 侧栏为终端式系统导航与状态模块；为 `SectionCard`、`StatusBanner`、`HeroMetrics` 增加终端语义结构并统一深色表面；将 `News Feed` 重命名和重构为 `Signal Desk / Primary Signal / Signal Queue / News Stream` 的终端化阅读流；将 `Dashboard` 收敛为 `Market Control / Signal Overview / Live Movers` 的控制台式总览；同时新增和更新组件/页面测试覆盖这些结构与文案钩子。
- 影响文件：
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/assets/main.css`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/common/SectionCard.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/common/SectionCard.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/common/StatusBanner.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/common/StatusBanner.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/dashboard/HeroMetrics.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/dashboard/HeroMetrics.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/news/LeadStoryCard.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/news/StoryStrip.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/components/news/StoryStrip.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run` 通过（11 个文件 / 19 个用例）；`npm --prefix frontend run build` 通过；Playwright 实测 `1400px/1280px/1050px/760px` 下 shell 与新闻网格按预期折叠，`Tab` 焦点在深色背景下保持可见
- 风险/后续事项：本轮主要覆盖共享框架、News Feed 和 Dashboard，其余详情页与设置页主要继承新 token，尚未逐页做更深的视觉微调；开发态仍会对不存在的 `/api/stream/events` 打出 404 console 错误，但当前 mock/降级路径不受影响

## 2026-03-18 01:37

- 修改人：Codex
- 修改范围：前端终端化 UI 改造设计与实现计划文档
- 变更内容：新增前端终端式 UI 改造的设计文档与实现计划，明确从暖色杂志风切换为冷色金融终端风的目标，收敛橙色主信号与蓝色系统信号的语义边界，并把全局 token、AppShell、共享卡片、News Feed、Dashboard、响应式和验证拆成可执行任务。
- 影响文件：
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/docs/superpowers/specs/2026-03-18-frontend-terminal-ui-design.md`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/docs/superpowers/plans/2026-03-18-frontend-terminal-ui-plan.md`
  - `/Users/xiuyang/.config/superpowers/worktrees/news-caught/codex/frontend-terminal-ui/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：设计与计划文档已落盘；spec 与 plan 各经过独立 reviewer 检查并按反馈补齐验收边界、测试归属与响应式验证要求
- 风险/后续事项：当前仅完成文档阶段，尚未进入前端代码实现；后续执行时需严格保持路由和数据流不变，并验证深色主题下的可读性和焦点态

## 2026-03-18 00:48

- 修改人：Codex
- 修改范围：News Feed supporting stories 横向卡片布局、前端测试、设计与计划文档
- 变更内容：为 `Supporting Stories` 区块补充独立的 supporting 卡片结构，将原先标题和摘要纵向堆叠的高卡片改成更紧凑的横向信息卡；桌面端保持 3 列，平板降为 2 列，手机降为 1 列；同时新增组件测试覆盖 supporting 卡片专用 body/meta 包裹层，并补充本轮设计与实现计划文档。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/frontend/src/components/news/StoryStrip.vue`
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/frontend/src/components/news/StoryStrip.test.ts`
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/docs/superpowers/specs/2026-03-18-supporting-stories-horizontal-layout-design.md`
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/docs/superpowers/plans/2026-03-18-supporting-stories-horizontal-layout-plan.md`
  - `/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/news/StoryStrip.test.ts` 先失败后通过（1 个文件 / 1 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 3/2/1 列切换断点采用 `1099px` 和 `768px`，如果你希望平板更早或更晚切成双列，可以继续微调 [`/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/frontend/src/components/news/StoryStrip.vue`](/Users/xiuyang/.codex/worktrees/news-caught-frontend-polish/frontend/src/components/news/StoryStrip.vue) 中的媒体查询阈值

## 2026-03-17 23:52

- 修改人：Codex
- 修改范围：LLM 设置页、配置更新保留 key 语义、前后端测试
- 变更内容：后端 `POST /api/llm/config` 现在在首次创建时要求提供 `api_key`，但编辑既有配置时允许空 key 并保留后端原值，避免前端设置页误清空已保存的密钥；前端新增独立的 `LLM Settings` 页面、`/settings/llm` 路由、左侧导航入口和 `llmStore`，支持查看当前活动配置、编辑 provider/display/base_url/model，并在不重输 key 的情况下保存；新闻详情页改为从 `llmStore` 读取配置状态；同时补充设置页测试和后端 preserve-key 测试。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/api/routes/llm.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/repositories/llm_provider_config_repository.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/schemas/llm.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/tests/test_llm_config.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/stores/llmStore.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/LlmSettingsView.vue`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/LlmSettingsView.test.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/NewsDetailView.test.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/specs/2026-03-17-llm-settings-page-design.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/plans/2026-03-17-llm-settings-page-plan.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（30 个用例）；`npm --prefix frontend run test -- --run` 通过（4 个文件 / 11 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前设置页仍然基于后端单租户明文存储 key 的假设，适合内部个人使用，不适合直接开放到多用户生产场景；“空 key 保留原值”已解决误清空问题，但如果未来要支持显式删除 key，需要再补单独的删除动作和更清晰的交互

## 2026-03-17 23:18

- 修改人：Codex
- 修改范围：LLM 设置页设计与实现计划文档
- 变更内容：新增 `LLM Settings` 页的设计文档与实现计划，明确单活动配置表单、前端独立设置页入口，以及后端配置更新时“空 key 保留原 key”的语义，作为下一阶段让用户直接在页面中录入和维护大模型配置的实现基线。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/specs/2026-03-17-llm-settings-page-design.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/plans/2026-03-17-llm-settings-page-plan.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：设计与计划文档已落盘，内容与当前后端配置接口和下一阶段 UI 目标对齐自检
- 风险/后续事项：当前仅完成 spec 和 implementation plan，尚未进入代码实现；后续需要谨慎处理“保留原 key”与“显式清空 key”的交互边界

## 2026-03-17 23:00

- 修改人：Codex
- 修改范围：新闻详情页 LLM 标的分析、多 provider 配置接口、分析结果持久化、前后端测试
- 变更内容：后端新增 `LLM` 配置表、分析结果表、配置仓储、分析仓储、`openai-compatible` provider 和新闻分析服务；新增 `GET/POST /api/llm/config` 及 `GET/POST /api/news/{id}/analysis|analyze` 接口，支持后端保存当前活动 provider/model/API key，并对单条新闻手动触发结构化分析，返回首选标的、候选列表、摘要、风险提示与上下文限制；前端扩展 API 类型、client、mock 和 `newsStore`，在新闻详情页新增“LLM 标的分析”区块，支持未配置空状态、加载态、重新分析和结果展示；同时补充后端配置/分析测试与前端详情页测试。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/api/router.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/api/routes/llm.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/models/llm_provider_config.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/models/news_analysis_result.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/repositories/llm_provider_config_repository.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/repositories/news_analysis_repository.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/schemas/llm.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/app/services/news_analysis.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/tests/test_llm_config.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/tests/test_news_analysis.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/frontend/src/views/NewsDetailView.test.ts`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/specs/2026-03-17-llm-news-analysis-design.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/plans/2026-03-17-llm-news-analysis-plan.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（28 个用例）；`npm --prefix frontend run test -- --run` 通过（3 个文件 / 9 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 API key 仍为后端单租户明文存储方案，适合你个人先用，不适合直接多人共享；第一版 provider 实现只做 `openai-compatible` 协议抽象，后续若接 `Anthropic/智谱/通义` 仍需补具体 client；分析结果是模型建议而非事实字段，也未与自选股或自动操作联动

## 2026-03-17 17:18

- 修改人：Codex
- 修改范围：LLM 新闻标的分析实现计划文档
- 变更内容：新增新闻详情页手动触发 LLM 标的分析的实现计划，按 provider 配置持久化、新闻分析结果落库、后端分析接口、前端详情页交互和验证步骤拆成可执行任务，并明确每个任务先写失败测试再实现。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/plans/2026-03-17-llm-news-analysis-plan.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：计划文档已落盘，内容与已确认 spec 对齐自检
- 风险/后续事项：当前仅完成 implementation plan，尚未进入代码实现；实际落地时需要继续处理 API Key 存储安全边界和 provider 错误语义

## 2026-03-17 22:32

- 修改人：Codex
- 修改范围：候选合并分支审查修正、测试初始化、本地产物清理
- 变更内容：在审查 `codex/invalid-request` 时补充后端测试初始化夹具，确保新闻相关测试在创建 `TestClient` 前完成数据库建表和种子初始化，消除 `news_item/article_content` 缺表导致的 5 个失败用例；同时恢复仍被 README 引用的 `ANGENT.md`，并移除误提交的 `.superpowers` brainstorm 产物与 `backend/news_caught.db`，补充 `.gitignore` 以避免再次入库。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/backend/tests/conftest.py`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/.gitignore`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/ANGENT.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests` 通过（21 个用例）；`npm --prefix frontend test -- --run` 通过（3 个文件 / 7 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次只修正了候选分支可合并性问题，未处理同一 worktree 中已有但与本次审查无关的未提交设计文档和记录变更

## 2026-03-17 17:10

- 修改人：Codex
- 修改范围：LLM 新闻标的分析设计文档
- 变更内容：新增新闻详情页手动触发 LLM 标的分析的设计文档，明确多 provider 抽象、后端统一保存活动 provider 配置、单条新闻结构化分析结果落库，以及与 `X Monitor/grok-bridge` 链路隔离的边界；同时约束第一版仅支持详情页手动触发，不接入新闻抓取、定时分析或自动交易动作。
- 影响文件：
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/superpowers/specs/2026-03-17-llm-news-analysis-design.md`
  - `/Users/xiuyang/.codex/worktrees/5132/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：设计文档已落盘，内容与已确认的产品边界和架构方向自检一致
- 风险/后续事项：当前仅完成 spec，尚未进入 implementation plan 与代码实现；`ANGENT.md` 在主仓库约束中仍被引用，后续交付时需继续确认记录要求的一致性

## 2026-03-17 16:12

- 修改人：Codex
- 修改范围：新闻详情页正文区块精简、前端视图测试补齐、设计与计划文档
- 变更内容：移除新闻详情页中冗余的“正文内容”卡片，不再在页面内展示正文抓取结果、抓取状态与错误信息，保留头部 `打开原文` 作为查看完整正文的唯一入口；补充 `NewsDetailView` 组件测试，约束详情页继续保留原文链接且不再渲染正文抓取区块；同步新增本轮前端精简的设计文档与实现计划。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/package.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/package-lock.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/vitest.config.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-17-news-detail-body-section-removal-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-17-news-detail-body-section-removal-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts` 通过；`npm --prefix frontend run test -- --run` 通过（3 个文件 / 7 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮仅移除前端正文展示，不删除后端正文抓取与 `article` 返回字段；工作区仍存在大量非本轮引入的未提交改动和 `ANGENT.md` 删除状态，本轮未处理

## 2026-03-17 15:58

- 修改人：Codex
- 修改范围：新闻正文抓取回填、发布时间优先排序、前端时间兜底与启动刷新、修复设计/计划文档
- 变更内容：为 `MiniMax News` 新增详情页二次抓取与回填逻辑，可从详情页解析真实发布日期和正文内容，并为既有旧记录补写 `article_content` 与 `published_at`；新闻列表改为优先按 `published_at` 排序，前端新增新闻时间兜底 helper，在新闻详情、主题详情、News Feed 卡片及关联新闻里统一回退到 `fetched_at`；前端启动后会非阻塞触发一次 `/api/news/refresh` 并重新加载新闻/主题，减少页面停留在旧数据库快照的问题；同时补充本轮修复的设计文档、实现计划与针对 MiniMax 解析、旧记录回填、发布时间排序的测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/news_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/time.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/time.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/newsEditorial.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-17-news-freshness-body-fix-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-17-news-freshness-body-fix-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过；`npm --prefix frontend run test -- --run` 通过；`npm --prefix frontend run build` 通过；`make ingest-news` 实测 `MiniMax Music 2.5+` 已回填真实 `published_at=2026-03-04T00:00:00Z` 且详情接口 `GET /api/news/123` 返回 `article.extract_status=success`
- 风险/后续事项：目前 `MiniMax News` 11 条里仅 `MiniMax Music 2.5+` 这类中文详情页模式已确认成功回填，其他英文 slug 仍有失败记录，后续需要继续为不同详情页模板补解析分支；工作区仍存在非本轮引入的 `ANGENT.md` 删除状态和其他前端未提交改动，本轮未处理

## 2026-03-16 23:38

- 修改人：Codex
- 修改范围：News Feed 杂志流改版、新闻排序辅助、左侧导航重构、前端测试基础设施
- 变更内容：前端新增 `Vitest` 测试基础设施和新闻 editorial 排序/分组辅助；News Feed 改为封面头条、supporting stories 和顺序流的杂志式布局，移除新闻页对固定高度虚拟列表的依赖，修复长中文标题与摘要重叠问题；左侧导航改为上对齐的编辑台式侧栏，并同步调整全局表面和留白节奏。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/package.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/package-lock.json`
  - `/Users/xiuyang/Desktop/news-caught/frontend/vitest.config.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/newsEditorial.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/newsEditorial.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/LeadStoryCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/StoryStrip.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/common/SectionCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/assets/main.css`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run` 通过；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮未新增人工置顶头条能力，头条仍由前端规则推断；未在本会话内完成浏览器手动验收；工作区仍存在非本轮引入的 `ANGENT.md` 删除状态，未处理

## 2026-03-16 21:48

- 修改人：Codex
- 修改范围：News Feed 杂志流 UI 优化实现计划文档
- 变更内容：新增 News Feed 杂志流 UI 实现计划，按前端排序辅助、杂志流布局改造、固定高度列表移除、侧栏重构、验证与记录更新拆成可执行任务，并明确前端测试与构建验证入口。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-16-news-feed-magazine-ui-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：计划文档已落盘，内容与已确认 spec 对齐自检
- 风险/后续事项：当前仅完成 implementation plan，尚未进入代码实现；前端当前无现成测试基础设施，实施阶段将补入最小 Vitest 支撑

## 2026-03-16 21:40

- 修改人：Codex
- 修改范围：News Feed 杂志流 UI 优化设计文档
- 变更内容：新增 News Feed 杂志流 UI 设计文档，明确封面式头条、次级新闻顺序流、前端混合排序、左侧导航改为上对齐编辑台侧栏，以及本轮仅做前端展示层重构、不新增后端接口的边界。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-16-news-feed-magazine-ui-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：设计文档已落盘，内容与已确认设计方向自检一致
- 风险/后续事项：当前仅完成 spec，尚未进入 implementation plan 与代码实现；由于工作区存在非本轮引入的 `ANGENT.md` 删除状态，本次未处理该文件

## 2026-03-16 21:05

- 修改人：Codex
- 修改范围：自选股真实行情接入、批量总览与详情页、后端缓存与接口、依赖与文档
- 变更内容：后端新增真实行情 provider 抽象、符号规范化、行情服务和 `/api/market/watchlist`、`/api/market/symbols/{symbol}` 接口，并扩展 `price_snapshot` 缓存字段；前端将自选股总览切换到新行情接口，新增单股详情页，展示价格、涨跌、开盘、昨收、最高、最低、成交量和相关新闻；同步补充 `yfinance` 依赖、README 和 API 契约说明。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/price_snapshot.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/market_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/quote_provider.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/quote_service.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistTable.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/backend/pyproject.toml`
  - `/Users/xiuyang/Desktop/news-caught/requirements.txt`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/api-contract.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过；`npm --prefix frontend run build` 通过；新增 `backend/tests/test_market.py` 覆盖自选股行情总览和详情接口
- 风险/后续事项：当前默认免费源为 `yfinance`，稳定性和字段覆盖受 Yahoo Finance 公共接口影响；本轮未完成 A 股支持；本地已存在旧 `price_snapshot` 表时依赖启动时补列

## 2026-03-16 20:41

- 修改人：Codex
- 修改范围：自选股真实行情接入实现计划文档
- 变更内容：新增自选股真实行情接入 implementation plan，按后端行情服务、前端总览与详情页、依赖与验证拆成可执行的 TDD 任务，作为后续实现基线。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-16-watchlist-real-market-data-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：计划文档已落盘，已与已确认 spec 对齐自检
- 风险/后续事项：计划未经过子评审；当前环境无 subagent，将在本会话按该计划执行

## 2026-03-16 20:32

- 修改人：Codex
- 修改范围：自选股真实行情接入设计文档
- 变更内容：新增自选股真实行情接入设计文档，明确港股/美股范围、免费行情源优先的 provider 抽象、符号规范化、批量总览接口、单股详情页、缓存与错误状态设计，为后续实现和计划拆解提供基线。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-16-watchlist-real-market-data-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：文档已落盘，内容已按已确认设计自检
- 风险/后续事项：尚未进入实现；免费行情源的具体 provider 仍需在实现阶段结合真实联调结果确认兼容细节

## 2026-03-16 19:55

- 修改人：Codex
- 修改范围：开发流程约束、superpowers skill 接入说明
- 变更内容：将 `obra/superpowers` 的核心开发流程以仓库级 `AGENTS.md` 形式接入当前项目，明确需求设计、计划拆解、TDD、系统化调试、验证、评审、分支收尾等阶段必须使用的 skills；同时在 `README.md` 补充 superpowers skills 需要预先安装到 `~/.codex/skills` 且安装后需重启 Codex 的说明，便于后续会话按同一流程执行。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/AGENTS.md`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：已执行 `python /Users/xiuyang/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py --repo obra/superpowers --path skills/using-superpowers skills/brainstorming skills/writing-plans skills/executing-plans skills/test-driven-development skills/requesting-code-review skills/receiving-code-review skills/systematic-debugging skills/verification-before-completion skills/dispatching-parallel-agents skills/subagent-driven-development skills/using-git-worktrees skills/finishing-a-development-branch`，并确认上述 skills 已出现在 `~/.codex/skills`；项目文档改动已落盘
- 风险/后续事项：当前会话不会自动重新加载新安装的 skills，需重启 Codex 后的新会话才会按新 skill 集生效；`obra/superpowers` 的 hooks、commands、agents 目录未直接并入本仓库，目前以 skill 约束为主

## 记录模板

```md
## YYYY-MM-DD HH:MM

- 修改人：
- 修改范围：
- 变更内容：
- 影响文件：
- 接口/数据结构变化：有 / 无
- 验证情况：
- 风险/后续事项：
```

## 2026-03-16 16:20

- 修改人：Codex
- 修改范围：X Monitor 增强模块、grok-bridge 联动、前后端接口与页面、测试与文档
- 变更内容：新增独立的 X Monitor 模块，通过 `grok-bridge` 拉取关注博主的近期市场相关 X 内容；后端新增 `x_account`、`x_post`、`x_post_symbol_mention`、`x_source_health` 模型、仓储、桥接客户端、刷新服务与 `/api/x/*`、`/api/health/x` 接口；前端新增 `X Monitor` 页面、类型、store、导航入口和 mock 兼容层；补充账号白名单示例文件、桥接说明文档与 X 模块测试；现有新闻、主题、自选股和 SSE 主链路未改为依赖该模块。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/router.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_account.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_post.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_post_symbol_mention.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_source_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/x_account_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/x_post_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/x_source_health_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/grok_bridge_client.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/x_monitor_accounts.example.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/api-contract.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过；`npm --prefix frontend run build` 通过；新增 `backend/tests/test_x_monitor.py` 覆盖桥接客户端、刷新去重、X 接口启停与健康状态；现有后端测试继续通过
- 风险/后续事项：当前 `grok-bridge` 结果仍属于 AI 抽取，不等同于 X 官方原始数据；`X Monitor` 暂不做自动调度和主题聚合；若 `grok.com` 页面结构变化，桥接稳定性会受影响

## 2026-03-16 15:49

- 修改人：Codex
- 修改范围：智谱与 MiniMax 官方来源接入、新闻展示去重优化、抓取解析测试
- 变更内容：为新闻抓取层新增 `MiniMax News` 官方新闻源和 `Zhipu AI News` 官方新闻源；扩展 HTML 锚点列表与智谱内联 JSON 两类解析器，并补充对应测试；前端新增新闻内容去重工具，在新闻卡片、新闻流详情页和新闻详情页中，当标题、摘要、正文内容重复时自动折叠重复文案，避免同一条内容双重显示。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/news.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 已在本轮前通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过；`npm --prefix frontend run build` 通过；`make ingest-news` 实测新增 `MiniMax News` 11 条、`Zhipu AI News` 15 条
- 风险/后续事项：`MiniMax News` 当前来自官方新闻入口，发布时间字段未在列表页稳定暴露，因此暂时以抓取时间排序；智谱来源当前来自官网页面内联数据，如官网前端结构大改，解析器需要同步调整

## 2026-03-16 15:30

- 修改人：Codex
- 修改范围：公开新闻源抓取、来源健康观测、抓取命令与接口、A股市场支持、文档与测试
- 变更内容：新增公开新闻抓取服务，接入 `WSJ`、`The Verge`、`36Kr`、`SEC Press Releases`、`财联社电报` 五个可直接访问的数据源；新增 `POST /api/news/refresh` 手动刷新接口与 `GET /api/health/sources` 来源健康接口；新增 `make ingest-news` 命令和公司 IR 来源配置示例；前端市场类型扩展为 `cn` 并补充时区与筛选项；补充 RSS/HTML 解析测试与刷新接口测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/workers/news_fetcher.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/source_health_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/source_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/news_sources.example.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/pyproject.toml`
  - `/Users/xiuyang/Desktop/news-caught/requirements.txt`
  - `/Users/xiuyang/Desktop/news-caught/Makefile`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/time.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/api-contract.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过；`npm --prefix frontend run build` 通过；`make ingest-news` 实测抓取 86 条公开新闻并成功入库；`/api/news?limit=8`、`/api/news?market=cn&limit=5`、`/api/health/sources` 已本地验证通过
- 风险/后续事项：`Reuters` 公开站点当前会返回 JS/反爬拦截页，尚未接入；公司 IR 新闻页仍需提供具体公司或 URL；中文源目前以 `cn` 市场落库，若后续要细分 A 股/H 股需进一步拆分市场模型

## 2026-03-16 14:56

- 修改人：Codex
- 修改范围：新闻列表筛选、UTC 时间序列化、前端时间兜底、后端测试
- 变更内容：为 `GET /api/news` 接入 `market`、`q`、`source_name`、`sentiment_label`、`limit` 查询参数并下推到仓库查询；新增统一 UTC 时间类型，修正新闻、主题、行情和健康接口的时间输出为带 `Z` 的 ISO 8601；前端时间工具增加无时区字符串按 UTC 解析的兜底；补充新闻接口筛选与时间格式测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/news_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/common.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/topic.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/time.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：有
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过；本地请求已验证 `/api/news?market=hk&limit=1` 和 `/api/news?q=Tencent` 正确过滤；`/api/news/1` 时间字段已输出 `Z`；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前仍是本地种子数据，真实抓取、来源健康检查和正文抽取任务仍未接入外部数据源

## 2026-03-16 14:34

- 修改人：Codex
- 修改范围：主题详情页、新闻详情页、交互增强
- 变更内容：为主题详情页新增关键词过滤和“只看带原文链接”开关；为新闻详情页新增同主题来源的上一条/下一条导航，支持在单个主题下顺序浏览不同来源。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/TopicDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：前端构建通过，`make build-frontend` 已验证
- 风险/后续事项：当前股票高亮仍基于标题和摘要命中，后续如需更准确应直接使用新闻提及数据

## 2026-03-16 14:20

- 修改人：Codex
- 修改范围：项目初始化、前后端骨架、主题聚合交互、自选股联调、协作规范、仓库提交准备
- 变更内容：完成项目计划和技术文档体系；搭建 FastAPI 后端骨架与 SQLite 初始化、健康检查、新闻/主题/自选股接口；搭建 Vue 前端主页面、新闻详情、主题详情、自选股添加链路；增强主题详情页的分组、时间线、过滤、高亮和原文直达交互；新增协作规范 `ANGENT.md` 与代码变更记录机制；新增 `.gitignore`，避免把依赖、缓存、构建产物和本地数据库提交到仓库。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.gitignore`
  - `/Users/xiuyang/Desktop/news-caught/plan.md`
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/ANGENT.md`
  - `/Users/xiuyang/Desktop/news-caught/backend`
  - `/Users/xiuyang/Desktop/news-caught/frontend`
  - `/Users/xiuyang/Desktop/news-caught/docs`
  - `/Users/xiuyang/Desktop/news-caught/Makefile`
  - `/Users/xiuyang/Desktop/news-caught/requirements.txt`
  - `/Users/xiuyang/Desktop/news-caught/environment.yml`
  - `/Users/xiuyang/Desktop/news-caught/scripts/dev.sh`
- 接口/数据结构变化：有
- 验证情况：后端测试通过；前端构建通过；本地接口联调已验证 `health`、`watchlist`、`topics`、`news detail` 等关键链路
- 风险/后续事项：真实抓取和更大规模主题聚合仍需后续继续补强；本次提交前需确认 GitHub 私有仓库创建并成功推送

## 2026-03-16 14:08

- 修改人：Codex
- 修改范围：项目说明、并行开发协作约束
- 变更内容：将“每次修改必须回填代码记录文档”的要求同步写入 `README.md` 和并行开发文档，确保多线程开发时也默认执行该规则。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/README.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/parallel-development.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：文档已更新并落盘
- 风险/后续事项：后续所有开发线程仍需要主动遵守，否则记录机制只会停留在文档层面

## 2026-03-16 14:05

- 修改人：Codex
- 修改范围：协作规范、变更记录机制
- 变更内容：新增根目录 `ANGENT.md`，约束后续所有修改必须同步回填到代码记录文档；新增 `docs/code-change-log.md` 作为统一记录入口。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/ANGENT.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：文档已创建，内容已落盘
- 风险/后续事项：后续每次代码、配置、文档、脚本修改都需要同步更新本文件，否则记录机制会失效
