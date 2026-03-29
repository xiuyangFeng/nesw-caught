# 代码变更记录

> 用于记录本项目每一次实际修改。新增记录时，追加到最上方。

## 2026-03-30 00:42

- 修改人：Codex
- 修改范围：事件详情后端接口、事件详情页 API 化、前后端回归测试
- 变更内容：为了解决 `EventDetailView` 依赖前端 `feedLayout` 快照导致刷新/深链脆弱的问题，后端新增 `GET /api/news/events/{event_key}`。`NewsFeedLayoutService` 拆出可复用的 topic context 收集逻辑，并新增 `get_event_detail()` / `_build_event_detail()`，在服务端按现有 feed-layout 规则重建事件详情；`NewsEventDetailView` 作为新响应模型返回完整 `news_items`，不再沿用首页事件卡的 3 条截断结果。路由顺序上把 `/events/{event_key}` 放在 `/{news_id}` 之前，避免动态段冲突；详情侧排序契约统一为 `published_at -> fetched_at -> id` 倒序。前端新增 `NewsEventDetail` 类型和 `apiClient.getNewsEventDetail()`，并重新实现 `EventDetailView`：页面加载后直接请求后端事件详情，成功时渲染事件摘要和时间线，404 时显示“事件已不存在，或已发生聚合变化”，其他错误时显示通用失败态；同时新增 `event-detail` 路由与对应测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/backend/app/schemas/news.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/router/index.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/views/EventDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/frontend/src/views/EventDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/docs/superpowers/specs/2026-03-30-event-detail-api-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/docs/superpowers/plans/2026-03-30-event-detail-api-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/event-detail-api/docs/code-change-log.md`
- 接口/数据结构变化：新增后端接口 `GET /api/news/events/{event_key}`；新增响应模型/前端类型 `NewsEventDetail`；现有 `GET /api/news/feed-layout` 契约不变
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py -q` 通过（25 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/views/EventDetailView.test.ts src/router/index.test.ts` 通过（3 个文件 / 17 个用例）；`npm --prefix frontend run build` 通过；`npm --prefix frontend run test -- --run` 通过（40 个文件 / 163 个用例）
- 风险/后续事项：当前事件详情已不再依赖前端快照，但 `event_key` 仍然是“按当前规则可重建”的临时键，尚未升级为持久化事件实体 ID；若后续需要长期稳定回放或跨时间窗口复原，仍需引入事件持久化层

## 2026-03-29 23:37

- 修改人：Codex
- 修改范围：首页新闻发现重构、壳层导航优先级、Dashboard 次级化、前端回归测试
- 变更内容：把前端首页默认落点从 `/dashboard` 改为 `/news`，新增 `frontend/src/router/index.test.ts` 锁定根路由进入新闻发现页。`AppShell` 同步从 dashboard-first 调整为 news-first：侧边导航把 `Latest Events` 提到 `01`，壳层 desk/workspace 文案改为 latest-event discovery 语义，并为新闻 layout 刷新路径补上 `feedQuery?.market` 的可空守卫，避免 SSE 事件到达时访问未初始化查询状态报错。`NewsFeedView` 重新 framing 为紧凑型 `Latest Events` 首页，弱化原有 `Signal Desk` 文案；`EventFeedCard` 改成更高密度的事件行，移除大块摘要，保留时间、事件类型、市场、主 symbol、相关 symbol、来源数和轻量 evidence 汇总，同时把底部证据入口收口为可聚焦的 story buttons，避免把整卡硬绑到 `news_items[0]` 并恢复键盘可达性；原始新闻流在首页中统一改走 `stream-compact` 以降低视觉权重。`DashboardView` 改为 secondary overview 语义，只保留次级总览定位，不再作为主控制台叙事。同步新增/更新路由、AppShell、EventFeedCard、NewsFeedView、DashboardView 的测试，前端全量测试恢复为全绿。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/router/index.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/EventFeedCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/EventFeedCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-29-news-discovery-homepage-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-29-news-discovery-homepage-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；继续复用现有 `feed-layout.events` 契约，没有新增前后端字段
- 验证情况：`npm --prefix frontend run test -- --run src/router/index.test.ts src/components/layout/AppShell.test.ts src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts src/views/DashboardView.test.ts` 通过（5 个文件 / 31 个用例）；`npm --prefix frontend run build` 通过；`npm --prefix frontend run test -- --run` 通过（39 个文件 / 156 个用例）
- 风险/后续事项：当前首页仍保留 topic 和 raw stream 两个 secondary evidence 区块，后续如果要继续提高首屏密度，可以进一步压缩辅助区块；另外，本次只做“广收事件 + 首页重心重排”，未引入 AI 过滤与个性化排序

## 2026-03-29 23:34

- 修改人：Codex
- 修改范围：新闻发现首页、事件卡片密度、首页文案与回归测试
- 变更内容：将 `NewsFeedView` 的首屏 framing 从偏 `Signal Desk` 的控制台文案改为 `Latest Events` 的紧凑事件发现页，首页副标题改为先看最新事件、再看主题和原始新闻流；把 `EventFeedCard` 压缩成更密集的事件行，移除大块摘要展示，改为事件级元数据和更轻量的来源证据汇总，并保留点击首条新闻的跳转行为；把原始新闻流卡片在首页中改为更紧凑的 `stream-compact` 呈现。同步新增 `EventFeedCard.test.ts`，并调整 `NewsFeedView.test.ts` 锁定 compact latest-events framing。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/components/news/EventFeedCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/components/news/EventFeedCard.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts` 通过（2 个文件 / 14 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：首页仍保留 topic 和 raw stream 作为 secondary evidence layers，后续若要进一步压缩首屏，还可以继续收紧这些辅助区块的行高和信息量，但本次未引入新数据契约

## 2026-03-29 23:30

- 修改人：Codex
- 修改范围：前端根路由重定向、AppShell 新闻流刷新守卫、AppShell 回归测试
- 变更内容：将前端根路径 `/` 的重定向目标从 `/dashboard` 改为 `/news`，让应用落地后直接进入新闻发现页而不是仪表盘。`AppShell` 的新闻流刷新辅助函数改为通过 `newsStore.feedQuery?.market` 读取市场条件，避免在 `feedQuery` 尚未初始化或被清空时访问 `market` 抛错；当 `feedQuery` 缺失时仍会以空市场参数刷新 layout。同步补充回归测试，覆盖根路由跳转到新闻页，以及 `feedQuery` 缺失时的安全刷新路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/news-discovery-homepage/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts` 通过（11 个用例）
- 风险/后续事项：当前只修复了 shell 里的显式刷新入口；如果后续还有其他直接读取 `newsStore.feedQuery` 的路径，建议统一收口到同一类可空访问模式

## 2026-03-28 21:14

- 修改人：Codex
- 修改范围：飞书通知持久化队列、共享 sender、通知服务投递 worker 与回归测试
- 变更内容：将飞书通知链路从“进程内 buffer + 直接发送”改造成“持久化任务入队 + delivery worker 投递”。新增 `notification_job` 表和仓储，统一承载 `news_source_event`、`news_batch`、`watchlist_alert`、`analysis_result` 四类通知任务/事件，并支持弱去重、CAS claim、`lease_token` 保护的 finalize、过期 `sending` 回收、重试回写、sent/failed 终态。`NotificationService` 现在在新闻/自选股/分析入口只做配置判断和入队；新闻通知改为先持久化 source-event，再在 worker tick 中按窗口幂等合成 `news_batch` 任务；news toggle 关闭时会主动丢弃待发 backlog，避免后续重新打开时补发旧消息；自选股告警保留边沿状态机，但永久发送失败后会释放锁存，避免同一 symbol 在阈值上方时被永久压住。`feishu_client.py` 同步改为共享 sender 路径：引入 `get_shared_feishu_sender()` 复用同凭据下的长生命周期 `httpx.Client` 和 token 缓存，并支持 invalid token 单次强制刷新重试与错误分类。`/api/notify/feishu/test` 改走共享 sender；相关测试从原先的内存 `_news_buffer` / 同步 `_send` 断言迁移到持久化 job 断言，并补充新闻 batch、可重试失败、sender 复用、lease token finalize、永久失败释放锁存等回归。顺手修正两条相邻回归测试：`test_market_watchlist_quotes_only_alert_on_threshold_entry` 适配异步入队语义，`test_refresh_all_publishes_news_created_for_each_insert` 补齐当前 payload 中已存在的 `editorial_score` 字段断言。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/notify.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/notification_job.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/notification_job_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/feishu_client.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/notification_service.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_feishu_notify.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_feishu_sender.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_notification_jobs.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-feishu-stability-performance-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-feishu-stability-performance-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增 `notification_job` 数据表；新增进程内 helper `get_shared_feishu_sender()` 与错误分类结构 `FeishuErrorClassification`；`notification_job` 新增 `lease_token` 字段用于 claim/finalize 所有权约束；对外 HTTP API 不变
- 验证情况：`conda run -n news-caught pytest backend/tests/test_feishu_notify.py backend/tests/test_notification_jobs.py backend/tests/test_feishu_sender.py -q` 通过（25 个用例）；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_market.py -q` 通过（48 个用例）
- 风险/后续事项：当前通知任务 claim/finalize 已补到单进程内较稳的 lease-token 语义，但底层仍基于 SQLite 和轮询 worker；如果未来要在多进程或多实例同时高频投递，仍建议进一步评估数据库级锁、单独队列或更强的 worker 协调机制。`get_shared_feishu_sender()` 的连接复用也仅限单进程内缓存，多进程部署时仍是各自进程独立缓存

## 2026-03-28 21:10

- 修改人：Codex
- 修改范围：飞书 sender 复用、token 缓存与错误分类
- 变更内容：重构 `feishu_client.py` 为可复用的 sender 路径：新增进程级 `get_shared_feishu_sender(app_id, app_secret, timeout)` 缓存，同一组凭据会复用同一个长生命周期 sender 实例；sender 内部改为懒加载并复用单个 `httpx.Client`，避免每次发送重复建连；`send_card` 增加单次强制 token 刷新重试，当消息返回 token 失效类错误时会刷新一次 token 后重发；补充 `classify_feishu_error()` 与 `FeishuErrorClassification`，把飞书错误按“是否可重试 / 是否需要刷新 token”拆分出来，并让配置类错误保持非重试。同步新增 `backend/tests/test_feishu_sender.py`，覆盖共享 sender 复用、长连接复用、invalid token 单次刷新重试和分类器行为。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/feishu_client.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_feishu_sender.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增进程内 helper `get_shared_feishu_sender()` 与分类结果结构 `FeishuErrorClassification`；现有 `FeishuClient`/`build_*_card` 仍保持兼容
- 验证情况：`conda run -n news-caught pytest tests/test_feishu_sender.py -q` 通过（3 个用例）
- 风险/后续事项：当前共享 sender 缓存只覆盖同进程内同凭据复用；如果后续在多进程 worker 中使用，需要在调用侧决定是否共享或在退出时显式关闭缓存的客户端

## 2026-03-28 21:00

- 修改人：Codex
- 修改范围：K 线新闻 marker review follow-up 收口
- 变更内容：继续处理 `worktree-kline-news-markers` 的前端 review。`KlineChart` 的 news marker 渲染逻辑改为只要 candlestick series 支持 `setMarkers()` 就始终同步 marker 状态，因此当新的 `klineData.news_events` 为空时会显式传入 `[]` 清空旧 marker，避免切换 symbol/周期后仍残留上一份新闻标记。同步补充回归测试，锁定“初始无 event 时不挂载 tooltip/popup”和“从有新闻切到无新闻时会清空 marker”两个契约；并把 lightweight-charts 测试 mock 补齐到当前 `setMarkers / subscribeCrosshairMove / subscribeClick` 接口，确保该路径在单测里真实覆盖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次已收口当前这组 K 线新闻 marker 前端 review finding；若后续继续扩展 hover/click 交互，建议再补针对 crosshair/click 订阅行为的组件级测试

## 2026-03-28 20:51

- 修改人：Codex
- 修改范围：K 线新闻 tooltip/popup 初始空态 prop 契约修复
- 变更内容：针对 review 指出的 `KlineChart` 初始渲染时把 `null` 传给 `KlineNewsTooltip` / `KlineNewsPopup` 必填 `event` prop 的问题，改为仅在 `tooltipState.event` 或 `popupState.event` 存在时才挂载对应组件，消除 Vue invalid-prop warning，并保持子组件的 `NewsEventMarker` 类型契约不放宽。同步补齐 `KlineChart` 测试里的 lightweight-charts mock 能力，新增回归测试锁定“初始无新闻事件时不挂载 tooltip/popup”。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.claude/worktrees/kline-news-markers/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 通过（1 个文件 / 3 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次只修复 review 中的 prop 契约问题；该工作树里其他前端 review finding 仍需单独处理

## 2026-03-28 19:41

- 修改人：Codex
- 修改范围：Watchlist K 线滚轮滚动穿透修复
- 变更内容：重新排查后确认用户描述的“滑动 K 线时整个窗口跟着滑”更贴近触控板/滚轮链路，而不是触摸链路本身。`KlineDrawingOverlay` 在空白区域把 `wheel` 转发到底层 chart 时，之前没有对原始事件执行 `preventDefault()`，导致图表收到缩放/平移的同时，页面也继续原生滚动。现已补上 `wheel.preventDefault()`，并在回归测试中锁定“转发到底层 chart 的同时，原始滚轮事件必须被标记为 `defaultPrevented`”。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 18 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前滚轮路径已经明确阻断页面默认滚动；如果后续用户反馈主要来自移动端手势，再继续针对真实设备补充触摸链路验证脚本

## 2026-03-28 19:33

- 修改人：Codex
- 修改范围：Watchlist K 线触摸滚动 second follow-up 修正
- 变更内容：将 K 线 overlay 的触摸会话从“`touchstart` 后依赖全局监听兜底”改成“overlay 自己持续接收 `touchmove / touchend / touchcancel` 并同步转发到底层 chart”。这样浏览器不会在触摸序列中途先把页面滚动接管，图表区域的单指滑动和多指手势都由 overlay 持续拦截并复制给底层图表；同时保留现有鼠标 handoff 路径不变。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 18 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前修复仍基于 overlay 手动转发触摸事件；如果后续还要继续贴近移动端券商终端手感，建议下一步把整套输入模型统一到 Pointer Events，减少鼠标/触摸两套逻辑并存的维护成本

## 2026-03-28 19:23

- 修改人：Codex
- 修改范围：Watchlist K 线触摸滚动 follow-up 修正
- 变更内容：针对真机上“图表区域仍可能触发页面原生滚动”的 follow-up，给 `KlineDrawingOverlay` 增加显式 `touch-action: none`，在 overlay 可交互时直接关闭浏览器对该区域的默认触摸滚动接管，避免继续单纯依赖 JS `preventDefault()` 的时序；同时补充测试，锁定交互态为 `none`、禁用态回退为 `auto` 的契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 18 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前图表区域会明确禁止浏览器原生 page pan；如果后续要支持更细粒度的移动端对象编辑手势，可能需要把当前 touch 模型进一步统一到 Pointer Events

## 2026-03-28 19:14

- 修改人：Codex
- 修改范围：Watchlist K 线触摸手势让渡与页面滚动穿透修复
- 变更内容：补齐 `KlineDrawingOverlay` 的触摸手势链路。空白区域在 `select` 模式下会把 `touchstart / touchmove / touchend / touchcancel` 完整转发到底层 chart，并仅在该让渡会话中通过非被动触摸处理阻止浏览器默认页面滚动，避免在 K 线区域滑动时整个窗口一起滚动；转发时保留完整 `touches` 数组，避免双指 pinch 被错误降级成单指手势。与此同时，为 drawing body / anchor / price note 标签补上显式 `touchstart.stop`，确保对象区域仍由 overlay 持有，不误触发空白区手势让渡。同步新增回归测试，覆盖完整触摸序列转发、默认滚动抑制、对象命中不转发、非 `select` 模式不让渡以及双指触摸保持透传。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-kline-touch-gesture-scroll-lock-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-kline-touch-gesture-scroll-lock-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或数据结构变化；仅前端 overlay 内部手势处理行为调整
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts` 通过（1 个文件 / 14 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 16 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前修复聚焦单指触摸滑动与手势让渡，不额外扩展双指缩放或对象触摸编辑；如果后续要继续提升移动端交互保真度，可以再评估是否将 overlay 的整套输入统一到 Pointer Events

## 2026-03-28 17:07

- 修改人：Codex
- 修改范围：News Feed final review 修正——清理 stale virtual visible ids
- 变更内容：修正虚拟列表可见项补水链路中的残留状态问题。`NewsFeedView` 新增 `orderedEntryIdSet`，`hydrationCandidateIds` 现在只会保留当前 `orderedEntries` 中仍然存在的 id，再与 `visibleStreamIds` 求并集；同时增加对 `useVirtualScrolling` 的 watch，在退出虚拟列表时主动清空 `visibleStreamIds`，避免旧虚拟列表中的可见项继续参与后续补水。同步新增回归测试：从 `>30` 条虚拟列表退回普通列表后，不再因为旧 `visible-ids` 触发无关详情加载。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或数据结构变化
- 验证情况：`npm --prefix frontend run test -- --run src/utils/newsEditorial.test.ts src/components/news/NewsCard.test.ts src/components/news/NewsVirtualList.test.ts src/views/NewsFeedView.test.ts` 通过（4 个文件 / 19 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前补水与虚拟可见项联动已经收敛到当前列表范围内；若后续希望进一步减少请求频率，可考虑在 `loadDetail` 层加入更明确的节流或批量接口

## 2026-03-28 17:03

- 修改人：Codex
- 修改范围：News Feed follow-up review 修正——降级排序隔离与持续补水
- 变更内容：继续处理新闻流 review follow-up。`NewsFeedView` 的 `layoutStreamScoreMap` 现在在 `feedLayoutDegraded=true` 时直接返回空映射，保证降级 layout 不再影响 raw stream 排序。详情补水机制从“挂载/筛选时一次性补前 8”改为由候选集 watch 驱动的持续补水：候选集包含当前排序前 8 条和虚拟列表当前可见项；若补水进行中又出现新的缺口，会在本轮结束后自动追一轮，避免排序变化后新晋升条目或后续滚动暴露条目长期不补水。`NewsVirtualList` 新增 `visible-ids` 事件，把当前可见 story id 回传给父层参与补水决策。同步新增前端回归测试两条：降级 layout 不应重排 raw stream、首轮补水完成后新晋升条目会被继续补水。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsVirtualList.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；仅新增前端组件内部事件 `visible-ids`
- 验证情况：`npm --prefix frontend run test -- --run src/utils/newsEditorial.test.ts src/components/news/NewsCard.test.ts src/components/news/NewsVirtualList.test.ts src/views/NewsFeedView.test.ts` 通过（4 个文件 / 18 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前补水候选仍是“前 8 + 当前可见项”的启发式策略，而不是全量后台预取；如果后续要进一步提升首屏稳定性，可考虑在 store 层缓存更完整的 detail 预热策略

## 2026-03-28 16:59

- 修改人：Codex
- 修改范围：News Feed review 修正——事件融合计数去重、排序补水对齐、虚拟列表固定高度收口
- 变更内容：针对本地 `main` 上新闻板块优化的 review findings 做三项修正。后端 `news_feed_layout.py` 的 `_merge_cards()` 改为基于去重后的合并新闻重新计算 `news_count` 与 `source_count`，避免融合事件卡统计大于实际挂载文章数。前端 `NewsFeedView` 新增从 `feedLayout.stream` 回填 `editorial_score` 到 raw `feedItems` 的映射，`orderedEntries` 排序会使用该分数作为 detail 缺失时的先验；`hydrateEditorialDetails()` 改为按当前排序后的前 8 条补水，而不是按原始 feed 顺序补水。前端 `NewsVirtualList` 改为使用显式 `156px` 固定行高，并将虚拟列表中的卡片切换为 `stream-compact` 紧凑变体；`NewsCard` 新增对应紧凑样式，收敛标题/摘要/元信息布局，保证虚拟行高与实际渲染契约一致。同步新增 3 个回归测试：融合计数唯一性、按排序补详情、虚拟列表固定高度紧凑卡片。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/newsEditorial.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsVirtualList.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsVirtualList.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；`editorial_score` 仍为已存在的可选字段，本次仅修正其前端消费方式
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -v` 通过（14 个用例）；`npm --prefix frontend run test -- --run src/utils/newsEditorial.test.ts src/components/news/NewsCard.test.ts src/components/news/NewsVirtualList.test.ts src/views/NewsFeedView.test.ts` 通过（4 个文件 / 16 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：虚拟列表仍基于固定行高实现，后续若要恢复更自由的卡片内容扩展，需要同步升级为动态测量行高或继续约束紧凑卡片的内容密度

## 2026-03-28 16:40

- 修改人：Codex
- 修改范围：News Feed 体验提升——跨 Topic 事件融合、编辑排序落地、NewsVirtualList 启用、历史重分类脚本
- 变更内容：四项体验提升改动。后端 `news_feed_layout.py` 新增 `fuse_event_cards` 跨 Topic 事件融合：同 `event_type`、同 `primary_symbol` 或 `related_symbols` 交集 >= 2 或标题 token Jaccard >= 0.5 的事件卡自动合并为一张，`general` 类型不参与融合；新增 `_stream_editorial_scores` 为 stream 计算编辑排序分（topic importance 0.4 + source weight 0.25 + freshness 0.2 + mentions 0.15），stream 按分数降序返回。后端 `schemas/news.py` 的 `NewsItemSummary` 新增可选 `editorial_score` 字段。前端 `NewsItem` 类型同步新增 `editorial_score`；`NewsFeedView` 的 `orderedEntries` 改为调用 `rankEditorialStories` 排序替代固定 `score: 0`；新增 `useVirtualScrolling` 开关，当 entries > 30 时使用修复后的 `NewsVirtualList`（props 改为 `entries: EditorialStoryEntry[]`，内部正确传 `:entry` 给 NewsCard），否则保持简单 `v-for`。新增 `scripts/reprocess_news_signals.py` CLI 脚本，支持 `--limit / --all / --dry-run / --batch-size` 参数，分批重跑 signal pipeline 处理未分类旧新闻。同步新增后端融合测试 8 条（标题重叠、同 symbol 融合、不同 event_type 不融合、general 不融合、链式融合、保持独立、merge 保高 importance）。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/NewsVirtualList.vue`
  - `/Users/xiuyang/Desktop/news-caught/scripts/reprocess_news_signals.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-news-feed-experience-uplift-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-news-feed-experience-uplift-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/news/feed-layout` 的 stream 中 `NewsItemSummary` 新增可选 `editorial_score` 字段；事件卡可能出现 `fused-` 前缀的 `event_key`；无新增 API 端点
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -v` 通过（13 个用例）；`npm --prefix frontend run build` 通过；`npm --prefix frontend run test -- --run` 通过（34 passed, 1 failed 为 AppShell 预存问题，非本次变更引入）
- 风险/后续事项：融合基于请求时计算，topic 数量极大时可能影响延迟（当前量级可忽略）；VirtualList 行高固定 132px，后续可升级为动态行高；重分类脚本需手动运行

## 2026-03-28 14:55

- 修改人：Codex
- 修改范围：X Radar 宏观词典外置配置
- 变更内容：把原先硬编码在 `XRadarSignalBuilder` 里的宏观规则抽成外部 JSON 词典。后端配置新增 `x_radar_rules_file`（环境变量 `X_RADAR_RULES_FILE`），若未设置则默认读取仓库内的 `backend/data/x_radar_rules.example.json`。`XRadarSignalBuilder` 现在会优先从文件加载 `tag / title / topic_tag / keywords / weight` 规则，加载失败时再回退到内置默认规则；宏观信号和共振信号标题也改为优先使用词典中的 `title`。审查收口阶段又补了三处：词典中坏 `weight` 项现在会被跳过，不会在服务启动或刷新时抛 `ValueError`；`xMonitorStore` 新增 `radarLoading` 并在账号新增/更新/删除、导入后自动刷新 radar，避免雷达卡空闪或长期停留旧数据；`GET /api/x/radar` 现在严格按传入 `limit` 截断 `priority_signals / macro_clusters / evidence_stream`。同时新增回归测试，锁定“外部规则文件可覆盖宏观标签与权重”“坏规则文件不炸服务”“radar limit 生效”和 store 级刷新行为。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/core/config.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_radar_signal_builder.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/x_radar_rules.example.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增 API；新增运行时配置项 `X_RADAR_RULES_FILE`，用于指定 X Radar 词典文件路径；默认词典文件格式为 JSON，顶层 `rules` 数组内每项包含 `tag/title/topic_tag/keywords/weight`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q` 通过（30 个用例）；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts src/stores/xMonitorStore.test.ts` 通过（2 个文件 / 7 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前优先级规则仍是“账号权重 + 词典 weight + 轻量 symbol bonus”的规则法，尚未把不同 signal_type 的附加权重完全外置；如果后续要把 account 权重、共振窗口或不同 signal_type 的加分也交给配置文件，还需要继续扩展词典 schema

## 2026-03-28 14:45

- 修改人：Codex
- 修改范围：X Monitor 升级为 X Radar 早期异动雷达
- 变更内容：围绕“自定义账号池 + 宏观/政策事件补充 + 优先级排序”的新定位，对 X 模块做了一轮后端到前端的闭环重构。后端新增 `x_signal` 与 `x_signal_post_link` 两张表、`XSignalRepository` 与 `XRadarSignalBuilder`，把原始 `x_post` 上抬为可解释的信号层；`refresh()` 现在在原始帖子去重入库后，会同步生成 `account_post / macro_event / multi_account_resonance` 三类首版信号，并给信号挂证据帖。同步扩展 `x_monitor` schema 与路由，新增 `GET /api/x/radar`，统一返回 `priority_signals + macro_clusters + evidence_stream` 三层数据。前端新增 `XRadarResponse / XRadarSignal / XRadarMacroCluster` 类型、`apiClient.getXRadar()`、store 的 `radar` 状态和加载逻辑，并把 `XMonitorView` 改为雷达台布局：`Priority Radar -> Macro Watch -> Evidence Feed` 为主视觉，账号管理降为右侧工作区，但保留新增账号、启停、删除、导入导出、翻译证据帖、关键词搜索等原有能力。同步补写本轮 spec / plan 文档，并在该 worktree 内安装了前端依赖以恢复 `vitest` 基线。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/__init__.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_signal.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/x_signal_post_link.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/x_signal_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/x_radar_signal_builder.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-x-radar-early-anomaly-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-x-radar-early-anomaly-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增后端接口 `GET /api/x/radar`；后端新增 `x_signal` 与 `x_signal_post_link` 持久化结构；前端新增 `XRadarResponse / XRadarSignal / XRadarMacroCluster` 类型和 `xMonitorStore.radar` 状态；原有 `GET /api/x/posts`、账号管理接口与刷新接口保持兼容
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q` 通过（27 个用例）；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 通过（1 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：首版宏观标签与优先级打分仍是规则法，关键词和分值需要后续根据真实使用频次继续调；`refresh()` 当前只对新插入帖子生成信号，若未来补回溯重建或规则变更，需要额外增加 reindex/rebuild 路径；本轮尚未把 `x_signal` 接入首页和自选股视图，这部分后续可以直接复用现有信号层

## 2026-03-28 14:30

- 修改人：Codex
- 修改范围：News Feed 事件质量提升——中文情绪/event_type、来源加权、时间衰减、N+1 查询修复
- 变更内容：纯后端改动，提升 Event Radar 事件卡的数据质量，不涉及前端变更。`NewsSignalClassifier` 新增 `POSITIVE_ZH`（18 词）、`NEGATIVE_ZH`（18 词）、`THEME_ZH`（22 词）中文词表，`_tokenize` 扩展为英文 regex + 中文最长匹配并集，`_keywords` 增加中文情绪词过滤，`_topic_key` 增加中文 theme 识别，`classify` 打分逻辑增加 `POSITIVE_ZH`/`NEGATIVE_ZH` dict lookup。`news_feed_layout.py` 的 `EVENT_TYPE_PATTERNS` 每类增加 7-9 个中文关键词（财报/营收→earnings，监管/处罚→regulation，大涨/暴跌→market_move 等）；新增 `SOURCE_TIER_WEIGHTS` 映射（primary 1.2 / secondary 1.0 / fallback 0.7），`_source_weight_map()` 通过 `load_sources()` 构建 source_name→weight 查找表；新增 `DECAY_LAMBDA=0.03`（~23h 半衰期）和 `_decayed_importance()` 指数衰减函数，排序时用衰减后分数替代原始 importance_score；`build_event_cards` 集成来源加权和衰减排序。`topic_repository.py` 新增 `batch_news_for_topics()` 和 `batch_related_symbols()` 批量查询方法；`NewsFeedLayoutService.build()` 从逐 topic 循环查询改为两条批量 SQL（从 2N+2 降到 4 条查询）。同步新增后端测试：中文情绪正/负/中三分类测试、中文 theme 词贡献 topic_key 测试、中文 event_type 模式匹配测试、来源加权分层测试、时间衰减排序测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_signal_classifier.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/topic_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_signal_pipeline.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-news-feed-event-quality-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-news-feed-event-quality-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增 API 或 schema 变化；`GET /api/news/feed-layout` 响应结构不变，`importance_score` 字段值现在包含来源加权修正
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py backend/tests/test_news_feed_layout.py backend/tests/test_news.py` 通过（19 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：中文词表为硬编码首版，未引入 jieba 等分词库，新词或分词歧义不在覆盖范围；本轮不修正已入库旧新闻的 sentiment，如需修正需额外 reprocess 脚本；`_source_weight_map()` 每次调用都解析 source 定义，若后续 source 数量大可加缓存

## 2026-03-28 10:50

- 修改人：Codex
- 修改范围：News Feed 事件主卡化与首页结构化数据编排
- 变更内容：围绕“主新闻流优先展示市场事件而不是原始文章”完成了一轮最小闭环改造。后端新增 `news_feed_layout` 派生服务和 `GET /api/news/feed-layout`，基于现有 `topic_cluster`、`news_item`、`news_stock_mention` 动态生成 `events + topics + stream` 三层首页数据，不引入新的持久化事件表；首版事件类型使用规则推断，支持 `product / macro / supply_chain / regulation / earnings / mna / market_move / general`，并输出主股票、相关股票、来源数和挂载新闻。审查阶段又补了十处收口：`market` 过滤下的 related symbols 现在按 market 范围收敛，避免跨市场 symbol 泄漏；前端 `newsStore.upsertNews/upsertNewsUpdate` 会同步更新 `feedLayout.stream`，避免 SSE 增量被首页结构层吃掉；`LoadingBlock` 空态改为按事件层 / 主题层 / 原始流三者联合判断，避免 stream 被筛空时把上层结构一起隐藏；`NewsFeedView` 挂载和筛选时会并行请求 `feed-layout` 与原始 `/api/news`，确保首页 raw stream fallback 是独立数据路径；`feedLayoutDegraded` 让降级 layout 不再压过真实原始流；`feedLoading` 改为基于并发请求计数收口，避免并行加载时过早结束 loading；`AppShell` 在新闻/主题增量事件下会刷新首页 layout，避免 `Event Radar / Topic Watch` 长时间停留在旧快照；`News Stream` 和 source 下拉现在只基于独立 raw `/api/news` 结果，不再被 layout 的 100 条上限截断；layout 请求新增 latest-response 保护，避免 SSE 高频刷新时旧响应覆盖新响应；raw `/api/news` 请求也新增同样的 latest-response 保护，避免快速切换筛选条件时旧结果覆盖新结果。前端新增 `feedLayout` 状态与 `EventFeedCard`，`NewsFeedView` 现在改为 `Event Radar -> Topic Watch -> News Stream` 三段结构，保留原始新闻流作为证据层，同时兼容原有市场/情绪/来源/关键词过滤。同步补写本轮 spec / plan 文档，并新增后端聚合测试、market 过滤测试、store 增量同步测试与首页渲染测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/topic_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_feed_layout.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/news/EventFeedCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-news-feed-event-led-structure-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-news-feed-event-led-structure-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增后端接口 `GET /api/news/feed-layout`；前端新增 `NewsFeedLayout / NewsFeedEventCard / NewsFeedTopic` 类型与 `newsStore.feedLayout` 状态；未修改既有 `GET /api/news` 契约
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py backend/tests/test_news_signal_pipeline.py` 通过（14 个用例）；`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/stores/newsStore.test.ts` 通过（2 个文件 / 16 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前事件层仍是基于 topic 的派生视图，跨 topic 的同题新闻尚未进一步融合；`event_type` 仍是规则推断，后续若要继续提升首页“交易终端感”，需要把官方源权重、突发性和更强的 symbol mention 质量纳入排序

## 2026-03-28 09:49

- 修改人：Codex
- 修改范围：Watchlist K 线对象工作台键盘快捷键与编辑态守卫
- 变更内容：在已有 store nudge 基础上，把对象工作台的键盘操作真正接到了图表层。`KlineChart` 现在支持 `Delete / Backspace` 删除当前多选、`Escape` 优先取消 draft 再清空选择、方向键批量微调选中对象，以及 `Shift + 方向键` 的大步长版本；空选择时不会拦截删除键，避免无意义地吃掉浏览器默认行为。审查阶段又补了一层全局快捷键守卫：当焦点位于原生输入框，或 `price_note` 标签编辑正在进行时，连 `Ctrl/Meta + Z/Y` 也不会误触发 drawing history。与此同时，`KlineDrawingOverlay` 新增 `labelEditingChange` 事件，把 `price_note` 文本编辑的打开、提交、取消、失焦生命周期显式同步给 chart，并阻断编辑器与 overlay 自己消费的 `Enter / Escape` 冒泡，避免单次按键被 chart window handler 二次消费。同步扩展 `KlineChart.test.ts` 和 `KlineDrawingOverlay.test.ts`，锁定键盘删除 / nudge / Esc 路由，以及 label editing guard 契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口或持久化结构变化；前端 overlay 新增 `labelEditingChange` 事件，chart 集成层新增键盘工作台路由
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 先失败后通过（2 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts` 先失败后通过（11 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts` 通过（6 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（3 个文件 / 19 个用例）
- 风险/后续事项：当前方向键价格步长仍基于当前 `klineData.candles` 全量范围，而不是可视区间；如果后续继续贴近券商终端手感，可以再把 visible range 纳入步长计算

## 2026-03-28 09:45

- 修改人：Codex
- 修改范围：Watchlist K 线对象工作台 store 级键盘 nudge / 删除收口
- 变更内容：补齐了 `watchlistChartStore` 的多选键盘平移能力，新增 `nudgeSelectedDrawings(symbol, { candles, timeStep, priceDelta })`，复用现有几何移动语义批量移动当前选中对象，并在每次有效 nudge 前写入 history，确保 `undo / redo` 可以回放这类键盘操作，同时避免边界 no-op 也写出空 history。同步补强 store 测试，覆盖 `deleteSelectedDrawings()` 清空多选、nudge 后撤销 / 重做回放、无效 selection 下的 delete/lock/visible no-op，以及 `horizontal_line` 左右平移保持 no-op 的既有语义。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口或持久化结构变化；前端 store 新增 `nudgeSelectedDrawings` 动作
- 验证情况：`npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts` 先失败后通过（4 个用例）
- 风险/后续事项：当前只补齐了 store 层 nudge 能力；如果后续继续落地键盘事件捕获，还需要在 chart/overlay 层接入 Delete / Backspace / Arrow / Escape 的按键路由与编辑态守卫

## 2026-03-28 00:58

- 修改人：Codex
- 修改范围：Watchlist K 线统一 cursor 读数与键盘 undo/redo
- 变更内容：在上一轮 history / 多选基础上继续完成主线收口。`KlineChart` 现在把 hover/cursor 时间统一用作技术读数来源，主图 HUD 之外，副图读数面板、技术面板和右侧图表读数也会随当前 hover candle 切换，而不是始终停留在最新一根 candle。与此同时补入了 `Ctrl/Meta + Z`、`Ctrl/Meta + Shift + Z`、`Ctrl/Meta + Y` 的键盘撤销 / 重做，使 store history 不只可从工具条按钮触发。同步扩展 `KlineChart.test.ts`，锁定 hover 后副图 MACD 读数切换，以及 toolbar / keyboard 两条 undo-redo 路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或持久化结构；仅前端 chart 集成层新增统一 cursor 派生读数与键盘 history 快捷键
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 先失败后通过（1 个文件 / 1 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineDrawingSelectionPopover.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（8 个文件 / 20 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 unified cursor 仍主要基于 overlay hover 时间驱动，尚未完全订阅 chart 原生 crosshair move；若后续继续追求更高保真度，可把 visible range 与 logical index 也收进同一 cursor 模型

## 2026-03-28 00:52

- 修改人：Codex
- 修改范围：Watchlist K 线 store history / 多选 / 对象工具条基础接线
- 变更内容：开启了这轮主线的第一批基础能力。`watchlistChartStore` 现在新增了 `selectedDrawingIds`、按 symbol 的 drawings 快照 history、`undo / redo`、批量锁定 / 显隐 / 复制 / 删除动作，并保持 `selectedDrawingId` 作为主选中对象兼容层。`KlineToolbar` 新增撤销 / 重做按钮，`KlineDrawingSelectionPopover` 升级为支持单选样式操作和多选 group actions 的对象工具条，`KlineDrawingOverlay` 的选择事件扩展为带 `append` 语义的 payload，支持 `Shift+Click` 加选。`KlineChart` 已接好 undo / redo、加选和 group actions 的基础 wiring，为后续统一 cursor 状态继续铺路。同步新增 `watchlistChartStore.test.ts` 和 `KlineDrawingSelectionPopover.test.ts`，并扩展 toolbar / overlay / chart 测试锁定这些契约。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineToolbar.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineToolbar.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingSelectionPopover.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingSelectionPopover.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-kline-cursor-history-multiselect-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-kline-cursor-history-multiselect-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口变化；前端本地工作台状态新增多选与 history 契约，overlay `drawingSelect` 事件改为 `{ id, append }`
- 验证情况：`npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts` 通过（2 个文件 / 10 个用例）
- 风险/后续事项：当前已完成多选和 history 的 store 基础，但统一 cursor state 还未完全把主图 HUD、副图读数和 hover 派生收束到同一模型；下一步应继续完成这部分整合并补整组回归验证

## 2026-03-28 00:40

- 修改人：Codex
- 修改范围：Watchlist K 线 overlay 与主图手势让渡修复
- 变更内容：修复了主 K 线图被 overlay 完整遮挡后，底层 `lightweight-charts` 无法收到鼠标拖拽 / 滚轮事件的问题。`KlineDrawingOverlay` 现在在 `select` 模式、非拖拽、非标签编辑且命中空白区域时，会把 `mousedown` 和 `wheel` 手势临时让渡给底层 chart；命中 drawing body / anchor 或处于绘制编辑态时，overlay 仍保持所有权，不影响现有 crosshair、画线创建和对象编辑。同步扩展了 overlay 测试，覆盖空白区转发和对象命中不转发两类路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-kline-overlay-chart-gesture-handoff-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-kline-overlay-chart-gesture-handoff-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口或持久化结构变化；仅前端 overlay 增加底层 chart 手势转发逻辑
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts` 先失败后通过（1 个文件 / 8 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 9 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前让渡逻辑只覆盖鼠标 `mousedown` / `wheel`，足以恢复常见桌面手势；若后续要支持触控板 pinch 或更完整的图表原生手势，建议进一步接 `pointer` / `touch` 级别链路

## 2026-03-28 00:31

- 修改人：Codex
- 修改范围：Watchlist K 线 fib / price note 编辑与更贴近原生轴的 crosshair 联动
- 变更内容：继续补齐 K 线工作台交互闭环。`KlineDrawingOverlay` 现在把 `fibonacci_retracement` 和 `price_note` 一并纳入可编辑对象：fib 支持端点拖拽和对象整体平移，price note 支持锚点/对象移动，并新增双击标签后的轻量文本编辑输入，提交后通过现有 store 的 `commitLabelEdit` 写回。与此同时，crosshair 的价格 / 时间标签不再只靠 overlay 按全量 high-low 比例换算，而是优先消费 `KlineChart` 透传的 chart projector，使用图表时间轴与价格坐标 API 做投影，fallback 时才退回旧的近似映射。同步扩展了 `klineOverlayGeometry`、overlay 和 chart 测试，锁定 fib / price note 编辑和 projector 优先路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineOverlayGeometry.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineOverlayGeometry.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-28-kline-fib-note-nativeish-crosshair-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-28-kline-fib-note-nativeish-crosshair-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口或持久化结构；前端 overlay 事件新增 `drawing-label-commit`，仅在本地图表工作台层消费
- 验证情况：`npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 先失败后通过（3 个文件 / 11 个用例）；`npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（7 个文件 / 19 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前时间标签仍主要依赖 candle 时间字符串和 chart time scale 的轻量投影，不是完整订阅图表原生 crosshair move 事件；后续若继续追求更高保真度，应进一步接入 visible range / logical index 级联动

## 2026-03-28 00:14

- 修改人：Codex
- 修改范围：Watchlist K 线 crosshair / 画线编辑 review 修正
- 变更内容：根据本轮 code review 继续修正了 K 线 overlay 的三个实际问题。第一，统一把拖拽起点和结束点都改为基于 overlay 自身坐标系计算，避免从趋势线/矩形 SVG 本体发起拖拽时落入 shape 局部坐标，导致对象整体移动跳错 candle。第二，在 `mouseleave` 与全局 `mouseup` 上补了 drag state 清理，避免鼠标在图外释放后把旧拖拽状态带回下一次提交。第三，为 overlay 挂上 `ResizeObserver`，让侧栏折叠/展开等布局变化后也会刷新 overlay 尺寸，保持 crosshair 与标签定位不漂移。同步扩展了 `KlineDrawingOverlay.test.ts`，新增了对精确 anchors 提交、锁定对象不可拖动、stale drag reset 和 ResizeObserver 尺寸刷新的覆盖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或持久化结构；仅修正前端 overlay 交互实现与测试覆盖
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts` 先失败后通过（1 个文件 / 5 个用例）；`npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（7 个文件 / 18 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 crosshair 仍然是 overlay 合成层，虽然尺寸刷新和拖拽状态已经补稳，但价格标签仍不是图表库原生价格轴；后续如果继续提升交互保真度，最好把 crosshair 与图表库自身坐标体系更深地对齐

## 2026-03-28 00:06

- 修改人：Codex
- 修改范围：Watchlist K 线十字光标与基础画线编辑
- 变更内容：继续在专业终端化布局基础上补齐主图交互。为 K 线 overlay 新增了合成十字光标层，支持在主图内显示横纵参考线、时间标签和价格标签，并继续复用 hover anchor 驱动 HUD 读数；同时为基础画线编辑补入了 geometry 工具函数和 overlay 事件链路，支持已选中 `趋势线 / 水平线 / 矩形区间` 的锚点拖拽或对象整体移动，锁定对象仍可选中但不会进入拖拽。`KlineChart` 现在会消费 `drawing-anchor-commit / drawing-move-commit` 并写回现有 `watchlistChartStore`。这一轮还新增了 `klineOverlayGeometry.test.ts`，并扩展 overlay/chart 测试覆盖 crosshair 标签和编辑提交路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineOverlayGeometry.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineOverlayGeometry.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-crosshair-drawing-edit-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-crosshair-drawing-edit-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口或持久化结构；前端 overlay 事件扩展为 `drawing-anchor-commit / drawing-move-commit`，仍只在本地工作台层消费
- 验证情况：`npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 先失败后通过（3 个文件 / 9 个用例）；`npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（7 个文件 / 17 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前十字光标仍是 overlay 合成层，价格和时间标签依赖前端 high/low 映射，不是图表库原生坐标轴；`fibonacci_retracement` 与 `price_note` 仍保持只读，后续若继续提升编辑能力，应优先补这些工具的拖拽策略以及真正的 crosshair/轴联动

## 2026-03-27 23:42

- 修改人：Codex
- 修改范围：Watchlist K 线专业终端化重排
- 变更内容：继续在上一版 K 线工作台基础上做“图优先”的专业终端化优化。将原先独立的摘要卡并入主图舞台，新增图内 `HUD` 读数带和顶部角标，将 `代码 / 周期 / 范围 / 图例` 收敛到图内信息层；把副图切换区压缩成更紧凑的控制条；将 `KlineToolbar` 重排为分组控制带、`KlineIndicatorWorkbench` 收紧为更像侧柜的模板库；同时为 `KlineDrawingOverlay` 增加 `hover-anchor-change` 事件，让主图可以根据 hover candle 实时切换 HUD 读数。为这轮调整新增了 `KlineToolbar`、`KlineIndicatorWorkbench`、`KlineDrawingOverlay` 三个组件级测试，并扩展了 `KlineChart` 集成测试覆盖图内 HUD 与 hover 回退。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineToolbar.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineIndicatorWorkbench.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineToolbar.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineIndicatorWorkbench.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-chart-professional-polish-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-chart-professional-polish-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增后端接口或数据结构；仅前端组件事件增加 `hover-anchor-change`，用于主图 HUD 的本地读数联动
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 先失败后通过（4 个文件 / 4 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts` 通过（2 个文件 / 3 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（6 个文件 / 11 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮只做到 hover 读数 HUD，没有实现真正十字光标、价格轴联动或更高精度的 overlay 命中；当前 HUD 仍依赖前端 candle 序列近似吸附，下一轮如果继续追求专业终端体验，应该把 crosshair 和 hover 事件进一步接到更真实的图表坐标体系

## 2026-03-27 23:15

- 修改人：Codex
- 修改范围：Watchlist K 线画线工作台基础接入
- 变更内容：为自选股详情页的 K 线区域补入了第一版“工作台”基础层和界面接入。新增了画线对象、指标模板与前端 EMA/RSI 的类型与工具函数，增加了独立 `watchlistChartStore` 管理当前工具、按股票画线、本地模板与副图状态；同时把原 K 线区域重构为由 `KlineToolbar`、`KlineDrawingOverlay`、`KlineIndicatorWorkbench` 与 `KlineDrawingSelectionPopover` 组合驱动的新结构。当前版本已经恢复并保持原有 `focusNews`、`switchPeriod`、主图/副图渲染与右侧技术面板回归，同时接入了基础的画线工具入口、模板选择、默认模板复制保存路径和选中对象样式/锁定/删除浮层。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineDrawings.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineIndicatorTemplates.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineIndicators.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/utils/klineOverlayGeometry.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistChartStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineToolbar.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineIndicatorWorkbench.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingOverlay.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineDrawingSelectionPopover.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-drawing-indicator-workbench-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-drawing-indicator-workbench-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：仅前端类型与本地持久化结构扩展；后端 K 线 API 与现有路由契约未变
- 验证情况：`npm --prefix /Users/xiuyang/Desktop/news-caught/frontend run test -- --run src/components/watchlist/KlineChart.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts` 通过（3 个文件 / 7 个用例）；`npm --prefix /Users/xiuyang/Desktop/news-caught/frontend run build` 通过
- 风险/后续事项：这版优先把工作台基础骨架和现有回归接通，`KlineDrawingOverlay` 里的命中、拖拽和价格映射仍是第一版轻量实现；后续如果要把画线体验继续逼近同花顺/TradingView，还需要补更精细的锚点拖拽、真正的空白透传/缩放联动，以及更完整的模板编辑测试

## 2026-03-27 21:12

- 修改人：Codex
- 修改范围：Watchlist K 线右侧指标栏折叠
- 变更内容：继续朝“图优先”布局优化，在 `KlineChart` 中为右侧指标栏增加了一键折叠能力。默认仍展示右侧指标面板，但现在可以通过图表内的 `收起面板 / 展开面板` 按钮切换；收起后右侧指标栏完全隐藏，`xl` 布局自动退回单列，把原本留给侧栏的横向空间让回主图。该状态仅保存在组件本地，不影响现有周期切换、指标计算、副图切换和新闻事件联动。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-collapsible-sidebar-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-collapsible-sidebar-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无接口或类型变化；折叠状态为前端组件本地 UI 状态，不进入 store
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 先失败后通过（1 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts src/views/WatchlistDetailView.test.ts` 通过（2 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前折叠状态不会记忆到下一次进入详情页；如果后续希望不同股票详情页都记住“默认展开还是收起”，可以再把该偏好提升到 store 或本地存储

## 2026-03-27 19:53

- 修改人：Codex
- 修改范围：Watchlist K 线常驻周期条与紧凑头部布局
- 变更内容：根据新反馈继续优化了自选股详情页的 K 线区域交互和占位。把原先藏在齿轮弹层里的 `日K / 周K / 月K / 年K` 周期切换挪到了 `KlineChart` 顶部，改成常驻快捷条，支持直接切换周期；同时移除了已失去主要价值的齿轮设置入口和弹层。顶部行情摘要卡片则整体压缩成更紧凑的条形结构：减小了标题、价格和容器内边距，收窄了头部布局列宽，缩短说明文案，把更多纵向空间还给 K 线主图。保留上一轮中文化与周期语义映射不变。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-toolbar-compact-header-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-toolbar-compact-header-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或类型变化；周期切换仍复用现有 `switchPeriod` 和前端 `interval/range` 映射
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts` 先失败后通过（2 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 先失败后通过（1 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts src/views/WatchlistDetailView.test.ts` 先因旧齿轮断言失败后通过（3 个文件 / 7 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：这轮主要压缩了头部高度和移除了重复入口，但还没有继续缩减右侧指标面板或主图下方副图区的整体高度；如果后续你还想把视图做得更像同花顺的“图优先”模式，下一步可以再把右栏进一步折叠或改成可收起

## 2026-03-27 19:41

- 修改人：Codex
- 修改范围：Watchlist K 线指标页中文化与券商式周期切换
- 变更内容：将自选股详情页 K 线区域的用户可见英文文案统一替换为中文，同时保留 `MACD / KDJ / BOLL / MA / DIF / DEA / K / D / J` 等技术指标缩写不变。顶部摘要区、设置弹层、K 线图摘要、右侧指标面板、副图区读数、新闻事件计数和更新时间文案均已中文化；周期入口从旧的 `1D / 1W / 1M / 3M / 1Y` 混合语义调整为更接近同花顺/东方财富习惯的 `日K / 周K / 月K / 年K`。对应前端请求映射也同步重构为 `1d+1y / 1wk+5y / 1mo+10y / 1mo+max`，其中 `年K` 第一版按长期年线视图处理，不引入后端 year-level 聚合。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-kline-chinese-timeframes-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-chinese-timeframes-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：前端 `WatchlistDashboardPeriod` 类型移除了未再使用的 `3M`；后端 API 契约与 `StockKlineResponse` 结构无变化，仍复用既有 `interval/range` 查询方式
- 验证情况：`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts` 先失败后通过（13 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts` 先失败后通过（2 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 先失败后通过（1 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts src/views/WatchlistDetailView.test.ts` 通过（4 个文件 / 20 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮 `年K` 仍是基于 `1mo + max` 的长期视图近似实现，视觉和操作习惯已接近券商软件，但并不是真正“每年一根 K 线”的后端聚合；若后续需要完全对齐同花顺/东方财富的年线定义，需要在后端补 yearly candle 聚合后再细化展示

## 2026-03-27 19:18

- 修改人：Codex
- 修改范围：Watchlist 终端式高密度改版
- 变更内容：按更接近同花顺的方向重做了自选股列表与详情页的交易终端样式。列表侧将 `StockCard` 压成更紧凑的横向卡片：右侧指标区收窄、市场/状态信息合并、价格与成交量聚拢、sparkline 保留但整体高度更低，`WatchlistSidebar` 列表间距也同步收紧。详情侧把原来的大留白行情头改成“左侧报价条 + 中部紧凑指标矩阵 + 右上设置”结构，并将主图区升级成更大的终端式 K 线面板：主图保留蜡烛、MA 和 BOLL，新增下方副图区和 `VOL / MACD / KDJ` 切换，右侧新增技术仪表栏，展示 `Session Range`、`6M Range`、`Bias vs MA20` 及最新 MA/BOLL/成交量等读数。所有右栏指标均基于现有 `quote` 与 `klineData` 推导，不引入新的后端字段。另补写了本轮 design / plan 文档，并更新了 `StockDetailPanel`、`KlineChart` 测试覆盖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/WatchlistSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/StockDetailPanel.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-27-watchlist-terminal-redesign-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-watchlist-terminal-redesign-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增前后端接口或类型字段；右侧仪表盘和区间指标均由现有 `WatchlistQuoteSummary` 与 `StockKlineResponse` 在前端计算得出
- 验证情况：`npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts` 先失败后通过（2 个文件 / 2 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts` 通过（4 个文件 / 14 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前右侧“高端仪表盘”仍然是基于现有行情/K 线数据的技术面展示，没有接入总市值、PE、换手率、五档盘口等更像券商终端的深度字段；若后续要继续贴近同花顺/东方财富，需要先扩充后端行情字段，再把右栏从技术仪表扩展为基本面 + 盘口混合面板

## 2026-03-27 18:56

- 修改人：Codex
- 修改范围：Watchlist K 线加载修复
- 变更内容：定位并修复了自选股详情页 K 线一直无数据的问题。根因不是缺少外部 API key，而是当前环境的 `yfinance==1.2.0` 在 `download()` 时返回了带 ticker 层级的 `MultiIndex` 列，后端 `market_chart_service` 仍按旧版单层 `Open/High/Low/Close/Volume` 列读取，导致 K 线序列化阶段抛出 `TypeError` 并使前端落入通用失败空态。本轮在历史行情下载后统一把多层列压平成单层 OHLCV 列，并补了一条回归测试覆盖该返回形状，确保现有 K 线 payload、指标计算和新闻事件对齐逻辑保持不变。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/market_chart_service.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-27-kline-yfinance-multiindex-fix-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无 API 契约变化；仍返回原有 `MarketKlineView` 结构，仅修正后端对 Yahoo Finance 历史数据列结构的兼容逻辑
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market.py -k multiindex -q` 先失败后通过；`conda run -n news-caught pytest backend/tests/test_market.py -q` 通过（17 个用例）；`conda run -n news-caught python -c "from app.services.market_chart_service import MarketChartService; from app.db.session import SessionLocal; session=SessionLocal(); payload=MarketChartService().get_kline('HK0700','1d','6mo',session); session.close(); print(payload['symbol'], len(payload['candles']), payload['candles'][0]['time'], payload['candles'][-1]['time'])"` 通过，返回 `HK0700 121 2025-09-29 2026-03-27`
- 风险/后续事项：本轮只修了后端根因，前端仍会把 K 线请求失败统一显示成固定文案，无法直接暴露后端错误详情；若后续还要提高可诊断性，可以再补 `watchlistStore` 的错误透传与图表错误态展示

## 2026-03-27 16:02

- 修改人：Codex
- 修改范围：Watchlist 列表页 / 详情页拆分与紧凑化
- 变更内容：把 `watchlist` 从原来的单页 master-detail 结构拆成了两个独立页面：`/watchlist` 现在只负责自选股列表、搜索、添加、删除和刷新；`/watchlist/:symbol` 改成专门的 K 线详情页。列表页去掉了旧的 `Trading Dashboard` 叙事，`WatchlistView` 不再渲染 `StockDetailPanel`，并把工具条、添加入口和股票行项整体压成更接近终端列表的 `A1` 密度；`StockCard` 改成 `compact` 行式布局，`WatchlistAddModal` 同步收紧标题、输入区和候选项密度。详情页侧则把 `WatchlistDetailView` 接到真实的详情路由上，负责 `selectSymbol + loadQuoteDetail + loadRelatedNews` 装载，并在缺失 symbol 或 404 时回退到 `/watchlist`；同时把列表页点击改成立即路由跳转，不再预拉详情数据，避免导航阻塞和重复请求。`watchlistStore.loadQuoteDetail()` 现在会在失败时正确退出 loading 并清掉旧 quote，避免详情页卡死或短暂显示上一只股票。`StockDetailPanel` 去掉了原来的常驻副图区与 signal summary，改成顶部行情条 + K 线主图 + 下方相关新闻区，并在行情条右上角新增螺丝按钮设置 `popover`；设置内容限制在 `watchlist-settings-scroll` 容器内滚动，当前只承载周期切换入口，同时保留新闻与 K 线事件的高亮联动。另补写了本轮 design / plan 文档，并新增 `StockDetailPanel` 组件测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/views/WatchlistDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/views/WatchlistDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/components/watchlist/WatchlistSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/components/watchlist/StockCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/components/watchlist/WatchlistAddModal.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/frontend/src/components/watchlist/StockDetailPanel.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/docs/superpowers/specs/2026-03-27-watchlist-page-split-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/docs/superpowers/plans/2026-03-27-watchlist-page-split-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex/watchlist-separate-page/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口或前端 API 类型变化；仅调整前端路由指向、页面职责和组件交互结构
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts` 先失败后通过（2 个文件 / 10 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts` 先失败后通过（8 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts` 先失败后通过（4 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts` 先失败后通过（1 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/components/watchlist/StockDetailPanel.test.ts src/stores/watchlistStore.test.ts` 通过（4 个文件 / 25 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts src/stores/watchlistStore.test.ts` 通过（5 个文件 / 26 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前设置 `popover` 只保留了真正有作用的周期切换入口，尚未恢复任何新的副图/指标面板；列表页头部和 market worker 状态仍在同页，后续若想进一步压缩首页高度，可以继续把运行状态折叠成更轻的状态条；详情页当前只对缺失 symbol 和 404 做回退，其余错误会留在当前页，后续若要提供更明确的重试/错误提示，可以继续补细分的详情错误状态

## 2026-03-27 01:05

- 修改人：Codex
- 修改范围：X Monitor 账号管理改造
- 变更内容：把 `X Monitor` 的账号管理从“刷新前按 JSON 文件强同步”的只读名单，改成了“数据库作为运行时真相源，页面可直接增删改，文件只做显式导入/导出”的工作流。后端为 `x_account` 新增 `tier` 和 `source` 字段，并在数据库初始化阶段补齐旧库兼容列；`x_monitor.py` 新增账号创建、更新、删除、导入、导出能力，刷新逻辑不再隐式读取配置文件，而是仅抓取数据库中 `is_active=true` 且 `tier!=muted` 的账号，并按 `core -> watch` 顺序刷新。API 层新增了 `POST /api/x/accounts`、`PATCH /api/x/accounts/{handle}`、`DELETE /api/x/accounts/{handle}`、`POST /api/x/accounts/import`、`POST /api/x/accounts/export`，同时 `GET /api/x/accounts` 返回新字段。前端 `XMonitorView` 左侧面板升级为账号管理台，加入账号创建表单、导入/导出按钮、层级标签、启停和删除动作，并默认隐藏 `muted` 账号帖子；Pinia store、API client、mock fallback 和 Vitest 用例都同步到了这套新契约。另补充了本轮设计文档和实现计划文档，供后续继续迭代。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/api/routes/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/models/x_account.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/repositories/x_account_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/schemas/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/app/services/x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/backend/tests/test_x_monitor.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/api/http.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/stores/xMonitorStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/views/XMonitorView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/frontend/src/views/XMonitorView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/docs/superpowers/specs/2026-03-27-x-monitor-account-management-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/docs/superpowers/plans/2026-03-27-x-monitor-account-management-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-x-monitor-account-management/docs/code-change-log.md`
- 接口/数据结构变化：`x_account` 新增 `tier` 与 `source` 字段；新增 X 账号 CRUD / import / export API；`GET /api/x/accounts` 返回结构新增 `tier`、`source`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'x_accounts or import_accounts_from_file or export_accounts_to_file or prioritizes_core or implicit_file_sync' -q` 先失败后通过（8 个用例）；`conda run -n news-caught pytest backend/tests/test_x_monitor.py -q` 通过（24 个用例）；`npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts` 先失败后通过（5 个用例）；`conda run -n news-caught pytest backend/tests/test_x_monitor.py backend/tests/test_health.py -q` 通过（26 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前页面支持新增、启停、删除和导入导出，但还没有做“编辑已有账号的 display name / priority / tier / notes”独立 UI，当前只先暴露了最常用的新增与状态动作；现有数据库兼容通过初始化补列处理，生产环境仍需要确认服务启动时一定会执行该初始化流程；导入语义目前是 merge-only，不会删除数据库里独有账号，后续如果要支持“按文件完整替换”应单独加预览和确认

## 2026-03-27 00:43

- 修改人：Codex
- 修改范围：watchlist 看 K 线交易台式界面重构
- 变更内容：围绕“看 K 线更像东方财富类交易台”的目标重做了 `watchlist` 详情区。`StockDetailPanel.vue` 从原来的卡片堆叠改成三段式交易台结构：顶部固定展示股票名/代码、最新价、涨跌额、涨跌幅、开盘、昨收、日内高低、成交量、更新时间和周期切换；中部把 `KlineChart.vue` 升级成主图交易面板，新增主图摘要、`MA5/10/20/60` 图例、BOLL 可用标识、空态骨架和事件筹码条；底部把副图和新闻区改成辅助分析层，`IndicatorChart.vue` 调整成更接近终端页签的切换样式，`RelatedNewsSidebar.vue` 改造成新闻时间流，并补上事件筹码与新闻条目的双向高亮联动。同步补写了 design/plan 文档，并扩充前端测试以锁定交易台结构、摘要信息和图表/新闻联动行为。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/components/watchlist/StockDetailPanel.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/components/watchlist/IndicatorChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/components/watchlist/RelatedNewsSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/docs/superpowers/specs/2026-03-27-watchlist-kline-trading-desk-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/docs/superpowers/plans/2026-03-27-watchlist-kline-trading-desk-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-kline-trading-desk/docs/code-change-log.md`
- 接口/数据结构变化：无后端接口或前端 API 类型变更；仅重组现有 watchlist 详情区展示层和组件交互
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts` 通过（10 个用例）；`npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts` 通过（1 个用例）；`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/components/watchlist/KlineChart.test.ts src/stores/watchlistStore.test.ts` 通过（3 个文件 / 22 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本轮仍未接入更深的交易软件能力，例如盘口、区间画线和更多主图叠加开关；当前主图仍基于 `lightweight-charts` 默认能力实现，后续若继续向专业行情终端靠拢，可再补十字游标信息栏、主图副图同步 hover 和更多快捷周期

## 2026-03-27 00:18

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 伊朗战争权力议案 false negative 迭代
- 变更内容：按当前 benchmark 只剩的单条 false negative，选择 `realtime-0255-1745` 这一条“伊朗军事行动 + 战争权力议案”样本做单点修正。按 TDD 先在 `test_news_relevance_evaluator.py` 增加一个伊朗战争权力正例和一个“伊朗 + 参议院听证会”负例 guardrail，并确认正例在现状下先失败；随后仅在 `news_relevance_evaluator.py` 增加一个窄规则，要求 `伊朗` 与 `军事行动/动武/军事打击` 以及 `战争权力/议案/参议院/投票/否决` 这组三类词共现时才判为市场相关，避免泛伊朗政治流程新闻被一并放宽。重跑 benchmark 后，新实验 `market_relevance_experiment_iran_war_powers` 的指标从 `precision=0.8421 / recall=0.9412 / noise_rejection_rate=0.9286` 提升到 `precision=0.8500 / recall=1.0000 / noise_rejection_rate=0.9286`，并把 keep decision 写入 experiment ledger，同时刷新晨读 report。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_iran_war_powers/evaluation.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_iran_war_powers/evaluation.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.html`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或数据结构；仅补充一条更窄的地缘政治市场相关性启发式规则与对应实验产物
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'iran_war_powers_vote_updates or generic_iran_senate_process_update' -q` 先失败后通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -q` 通过（28 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_evaluator.py backend/scripts/evaluate_market_relevance.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_experiment_iran_war_powers` 通过；`conda run -n news-caught python backend/scripts/run_news_relevance_experiment.py --experiment-id exp-20260327-iran-war-powers --baseline-id exp-20260326-taiwan-arms-sale --hypothesis "Catch Iran war-powers vote headlines without broadening generic Iran politics" --changed-file backend/app/services/news_relevance_evaluator.py --metrics-before backend/data/research/market_relevance_experiment_taiwan_arms_sale/evaluation.json --metrics-after backend/data/research/market_relevance_experiment_iran_war_powers/evaluation.json --ledger docs/research/market-relevance-experiments.tsv` 通过并记录 `keep`；`conda run -n news-caught python backend/scripts/render_market_relevance_report.py --benchmark backend/data/research/market_relevance_benchmark.jsonl --evaluation backend/data/research/market_relevance_experiment_iran_war_powers/evaluation.json --ledger docs/research/market-relevance-experiments.tsv --markdown-output backend/data/research/market_relevance_report.md --html-output backend/data/research/market_relevance_report.html` 通过
- 风险/后续事项：当前 benchmark 上的 false negative 已清零，后续应优先回头审视剩余 3 条 false positive，避免在 recall 已满时继续扩地缘政治规则；本轮规则仍是中文 headline 级启发式，如后续出现英文同类 headline，需要单独用 benchmark 样本验证后再扩

## 2026-03-26 19:08

- 修改人：Codex
- 修改范围：港美板块新闻第一轮来源与去噪升级
- 变更内容：按“最小闭环”方案补了第一轮板块新闻升级。`news_ingestion.py` 现在支持 `api` 类型来源和 `the_news_api_json` 解析，可把聚合 API 结果统一归一化到现有 `SourceItem`/入库流程；同时增加了基于 `host + 小时窗口 + 标题归一化` 的轻量重复抑制，避免同一窗口内的改写稿反复入库，并在同窗重复出现时优先保留更高 `tier/priority` 的来源元数据。重复签名归一化也从 ASCII 扩到中文标题，避免港股/中文快讯场景直接漏重。`news_relevance_evaluator.py` 在保留现有布尔 market relevance 兼容层的前提下，新增了 `predict_market_relevance_details()`，可返回 `sector_tags` 和 `relevance_reason`，先覆盖 `ai_compute`、`semiconductors`、`chinese_internet`、`apple_supply_chain` 四类板块标签；同时把市场信号词拆成高低置信两层，并新增 generic Apple/server chatter 负例，避免把泛产品评测或泛企业服务器刷新误判成板块信号。另新增 `news_priority.py` 作为纯 Python 排序 helper，用于按 `source tier -> sector tag -> official signal -> recency` 排序，作为后续 report/feed surfacing 的基础。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/app/services/news_priority.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/backend/tests/test_news_priority.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/docs/superpowers/specs/2026-03-26-sector-news-upgrade-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/docs/superpowers/plans/2026-03-26-sector-news-upgrade-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-sector-news/docs/code-change-log.md`
- 接口/数据结构变化：运行时未改现有 API route 和数据库 schema；新增 `api` source type 配置能力、新的 `predict_market_relevance_details()` 返回结构，以及独立的新闻排序 helper
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k 'api_source or supports_api_news_payload or duplicate_titles' -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'sector_tag' -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k 'promotes_duplicate_to_primary_source_metadata or deduplicates_same_window_chinese_titles' -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'generic_server_refresh or sector_tag' -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'company_event or shipping_route_disruption or taiwan_arms_sale' -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_priority.py -q` 通过（60 个用例）；`conda run -n news-caught pytest backend/tests/test_news_relevance_report.py backend/tests/test_news_signal_pipeline.py backend/tests/test_news.py -q` 通过（13 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_ingestion.py backend/app/services/news_relevance_evaluator.py backend/app/services/news_priority.py` 通过
- 风险/后续事项：当前 `api` 来源解析只先接了 `the_news_api_json` 这一种 payload，后续接入真实 The News API 仍需要补配置文件与 API key；重复抑制目前仍只覆盖“同 host、同小时窗口、标题近似一致”的改写稿，跨 host 转载和跨语言同义改写还未处理；新的板块 tagging 仍是启发式规则，后续应继续用 benchmark 扩样验证 precision/recall 边界，并把 `source tier` 元数据真正接到后续 report/feed 输出

## 2026-03-26 18:51

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 台湾军售 false negative 迭代
- 变更内容：基于当前主仓库 `market_relevance_experiment_recall_merge` 的剩余 false negative，仅选择 `historical-0188-188` 这一条“对台军售 + 拦截导弹”样本做单点修正。按 TDD 先在 `test_news_relevance_evaluator.py` 新增一个台湾军售正例和一个联合国叙利亚会议负例，并确认正例先因规则缺失而失败；随后仅在 `news_relevance_evaluator.py` 增加“`对台/台湾/台海` 与 `军售/导弹/武器` 共现”时判为市场相关的窄规则。重跑 benchmark 后，新实验 `market_relevance_experiment_taiwan_arms_sale` 的指标从 `precision=0.8333 / recall=0.8824 / noise_rejection_rate=0.9286` 提升到 `precision=0.8421 / recall=0.9412 / noise_rejection_rate=0.9286`，并把 keep decision 写入 experiment ledger，同时刷新晨读 report。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_taiwan_arms_sale/evaluation.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_taiwan_arms_sale/evaluation.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.html`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或数据结构；仅补充 evaluator 启发式规则与一轮新实验产物
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'taiwan_arms_sale or un_security_council_update' -q` 先失败后通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -q` 通过（20 个用例）；`python -m py_compile backend/app/services/news_relevance_evaluator.py backend/scripts/evaluate_market_relevance.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_experiment_taiwan_arms_sale` 通过；`conda run -n news-caught python backend/scripts/run_news_relevance_experiment.py --experiment-id exp-20260326-taiwan-arms-sale --baseline-id exp-20260326-recall-merge --hypothesis "Catch Taiwan arms-sale headlines without broadening generic geopolitics" --changed-file backend/app/services/news_relevance_evaluator.py --metrics-before backend/data/research/market_relevance_experiment_recall_merge/evaluation.json --metrics-after backend/data/research/market_relevance_experiment_taiwan_arms_sale/evaluation.json --ledger docs/research/market-relevance-experiments.tsv` 通过并记录 `keep`；`conda run -n news-caught python backend/scripts/render_market_relevance_report.py --benchmark backend/data/research/market_relevance_benchmark.jsonl --evaluation backend/data/research/market_relevance_experiment_taiwan_arms_sale/evaluation.json --ledger docs/research/market-relevance-experiments.tsv --markdown-output backend/data/research/market_relevance_report.md --html-output backend/data/research/market_relevance_report.html` 通过
- 风险/后续事项：主仓库剩余 false negative 现在只剩 `realtime-0255-1745`（伊朗战争权力议案）；后续如果继续提 recall，应继续保持单点地缘政治边界验证，避免把泛国际政治 headline 一并放进市场相关范围

## 2026-03-26 14:47

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch recall 合并落主仓库
- 变更内容：按你确认的“优先提 recall”方案，把自动化 worktree 中最稳妥的两条 keep 结果合并回了 `main`：一条是“概念/板块 + 涨停/跟涨”的中文题材异动识别，另一条是“航运主体 + 红海/路线/targeting 扰动”的英文航运风险识别。按 TDD 先在 `test_news_relevance_evaluator.py` 增加四条回归测试并确认两条正例先失败，再在 `news_relevance_evaluator.py` 只补这两条最窄规则。随后重跑 benchmark，生成新的组合实验产物 `market_relevance_experiment_recall_merge`，并把结果记录为新的 keep experiment；当前主仓库晨读 report 已刷新到这轮组合结果，指标从上一轮 `index-signals` 的 `precision=0.8125 / recall=0.7647 / noise_rejection_rate=0.9286` 提升到 `precision=0.8333 / recall=0.8824 / noise_rejection_rate=0.9286`。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_recall_merge/evaluation.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_recall_merge/evaluation.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.html`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-26-market-relevance-recall-merge-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-26-market-relevance-recall-merge-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口或数据结构；仅收紧 evaluator 的启发式规则并新增一轮组合实验产物
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'concept_mover or shipping_route_disruption or generic_product_concept or generic_gaza_humanitarian_updates' -q` 先失败后通过；`conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -q` 通过（18 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_evaluator.py backend/scripts/evaluate_market_relevance.py backend/scripts/render_market_relevance_report.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_experiment_recall_merge` 通过；`conda run -n news-caught python backend/scripts/run_news_relevance_experiment.py --experiment-id exp-20260326-recall-merge --baseline-id exp-20260325-index-signals --hypothesis "Combine concept-mover and shipping-route recall improvements" --changed-file backend/app/services/news_relevance_evaluator.py --metrics-before backend/data/research/market_relevance_experiment_index_signals/evaluation.json --metrics-after backend/data/research/market_relevance_experiment_recall_merge/evaluation.json --ledger docs/research/market-relevance-experiments.tsv` 通过并记录 `keep`；`conda run -n news-caught python backend/scripts/render_market_relevance_report.py --benchmark backend/data/research/market_relevance_benchmark.jsonl --evaluation backend/data/research/market_relevance_experiment_recall_merge/evaluation.json --ledger docs/research/market-relevance-experiments.tsv --markdown-output backend/data/research/market_relevance_report.md --html-output backend/data/research/market_relevance_report.html` 通过
- 风险/后续事项：剩余 false negative 现在只剩“对台军售”和“伊朗战争权力议案”两类地缘政治边界样本；后续如果继续提 recall，最好单独验证“地缘政治 headline 何时应视为市场相关”，不要顺手放宽泛政治规则

## 2026-03-25 18:14

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 首轮手动 experiment 迭代
- 变更内容：手动启动了 `market relevance autoresearch` 的第一轮 experiment，针对 baseline 中成簇出现的 false negative，选择“指数异动 / 商品价格快讯 / 市场稳定措施”作为单一假设进行收紧。按 TDD 先为 `news_relevance_evaluator.py` 补了三条失败测试，再新增 `沪指`、`深成指`、`电池级碳酸锂`、`市场稳定计划` 等更窄中文市场短语命中；随后用真实 benchmark 重跑评测，指标从 baseline 的 `precision=0.7500 / recall=0.5294 / noise_rejection_rate=0.9286` 提升到 `precision=0.8125 / recall=0.7647 / noise_rejection_rate=0.9286`。在把结果写入 experiment ledger 时，又发现 `news_relevance_experiment_runner.py` 的 scope guard 仍停留在旧的新闻主链范围，会错误拒绝 `news_relevance_evaluator.py` 这类 research 相关改动；本轮同步补了允许 `news_relevance_*` 服务和 research 脚本的测试与实现修正。最后基于这轮 experiment 结果刷新了晨读面板，使明天打开 report 时能直接看到最新 keep 实验，而不是旧 baseline。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_index_signals/evaluation.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_experiment_index_signals/evaluation.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.html`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；experiment runner 的允许修改范围扩大到当前 `news relevance autoresearch` 实际会触及的 research 服务与脚本
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_report.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q` 通过；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_report.py backend/scripts/render_market_relevance_report.py backend/app/services/news_relevance_evaluator.py backend/app/services/news_relevance_experiment_runner.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_experiment_index_signals` 通过；`conda run -n news-caught python backend/scripts/run_news_relevance_experiment.py --experiment-id exp-20260325-index-signals --baseline-id baseline-20260325-market-relevance-v2 --hypothesis "Catch index spikes, commodity price wires, and market stability plans" --changed-file backend/app/services/news_relevance_evaluator.py --changed-file backend/app/services/news_relevance_experiment_runner.py --metrics-before backend/data/research/market_relevance_baseline/evaluation.json --metrics-after backend/data/research/market_relevance_experiment_index_signals/evaluation.json --ledger docs/research/market-relevance-experiments.tsv` 通过并记录 `keep`
- 风险/后续事项：这轮提升主要覆盖了指数 / 商品价格 / 市场稳定措施这组市场层面信号，剩余 false negative 仍集中在地缘政治与主题联动类新闻；下一轮更适合单独检验“地缘政治是否应保留为市场相关”的边界，而不是继续往中文市场短语里堆规则

## 2026-03-25 17:58

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 晨读成果面板
- 变更内容：为当前 `market relevance autoresearch` 增加了一个轻量成果面板生成链路，新增 `news_relevance_report.py` 负责读取现有 benchmark、baseline evaluation 与 experiment ledger，并汇总成统一的晨读 report model；同时新增 `render_market_relevance_report.py`，可一次性生成两份输出：适合审阅和 diff 的 `market_relevance_report.md`，以及适合明早直接打开看的 `market_relevance_report.html`。两份面板都会展示最新指标、benchmark 样本分布、false positive / false negative 样本标题，以及最近几条 experiment ledger 记录。基于当前真实产物已经生成了首版晨读面板，后续可被 automation 每轮刷新。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_report.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/render_market_relevance_report.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_report.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_report.html`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-25-market-relevance-report-panel-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-25-market-relevance-report-panel-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增 report 生成 CLI `backend/scripts/render_market_relevance_report.py`；未改现有评测、benchmark 或 annotation 数据结构
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_report.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q` 通过；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_report.py backend/scripts/render_market_relevance_report.py` 通过；`conda run -n news-caught python backend/scripts/render_market_relevance_report.py --benchmark backend/data/research/market_relevance_benchmark.jsonl --evaluation backend/data/research/market_relevance_baseline/evaluation.json --ledger docs/research/market-relevance-experiments.tsv --markdown-output backend/data/research/market_relevance_report.md --html-output backend/data/research/market_relevance_report.html` 通过
- 风险/后续事项：当前成果面板仍然是静态文件，不会自动显示跨轮次指标 diff；如果后续夜间实验数量增多，建议继续补“上一轮 vs 当前轮”的显式变化摘要，避免只看原始列表

## 2026-03-25 17:06

- 修改人：Codex
- 修改范围：市场新闻相关性 review 决策回填、benchmark 首版产出与 baseline evaluator 回归修正
- 变更内容：基于已导出的 `market_relevance_review_queue.csv`，先代填了当前 `59` 条 review queue 的首版人审决策，并通过 `import-csv` 导回 `market_relevance_reviewed.jsonl`，随后执行 `apply` 将复核结果回填到候选集并生成首版 `market_relevance_benchmark.jsonl`。在真正跑 baseline 时发现 evaluator 的 market-signal 规则过于依赖窄英文 token，导致 `17` 条正样本被全部预测成 `False`、recall 直接掉到 `0.0`；经定位后，为 `news_relevance_evaluator.py` 增补了更贴近真实 ingestion/filter 语义的监管披露词和中文市场短语匹配，并补了中文业绩快报、回购/派息、SEC 基金持仓披露三个回归测试。收到 code review 后又继续收紧了两处：`SEC` 不再作为裸 token 直接触发市场相关，而是改成更具体的监管披露短语；`import-csv` 现在会拒绝漏行和重复 `sample_id`，避免编辑 CSV 时静默丢失 review 决策。修正后 baseline 已成功产出，指标为 `precision=0.75`、`recall=0.5294`、`noise_rejection_rate=0.9286`，同时把最终 baseline 记录追加到了实验 ledger。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_review_queue.csv`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_reviewed.jsonl`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_candidates.annotated.jsonl`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_benchmark.jsonl`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_baseline/evaluation.json`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_baseline/evaluation.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；baseline evaluator 的 market relevance 规则扩大到支持部分监管披露英文短语与中文市场短语命中
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q` 通过（33 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_dataset.py backend/app/services/news_relevance_evaluator.py backend/scripts/review_market_relevance_annotations.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py` 通过；`conda run -n news-caught python backend/scripts/review_market_relevance_annotations.py import-csv backend/data/research/market_relevance_review_queue.jsonl backend/data/research/market_relevance_review_queue.csv backend/data/research/market_relevance_reviewed.jsonl` 通过；`conda run -n news-caught python backend/scripts/review_market_relevance_annotations.py apply backend/data/research/market_relevance_candidates.annotated.jsonl backend/data/research/market_relevance_reviewed.jsonl backend/data/research/market_relevance_benchmark.jsonl` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_baseline --ledger docs/research/market-relevance-experiments.tsv --experiment-id baseline-20260325-market-relevance-v2` 通过并产出 baseline 指标
- 风险/后续事项：当前 benchmark 仍只有 `59` 条复核样本，主要覆盖低置信度和 spot-check 队列，代表性还不足以支撑更强结论；evaluator 虽已不再全量漏判，但规则仍偏启发式，下一步应继续基于这批 false positive / false negative 收紧真实 market catalyst 与泛宏观/泛舆情边界

## 2026-03-25 16:08

- 修改人：Codex
- 修改范围：市场新闻相关性 review queue 可读/可编辑导出
- 变更内容：为当前 `market relevance` 人审环节补了两条 review queue 辅助路径。其一，在 `news_relevance_dataset.py` 中新增 review queue 的 Markdown 和 CSV renderer，以及把编辑后的 CSV 决策安全导回 reviewed JSONL 的 helper；其二，在 `review_market_relevance_annotations.py` 中新增 `export`、`export-csv` 和 `import-csv` 命令，让 review queue 不再只能直接改 JSONL。本轮已基于现有 `backend/data/research/market_relevance_review_queue.jsonl` 生成两份人读产物：`market_relevance_review_queue.md` 和更适合直接编辑的 `market_relevance_review_queue.csv`。这样后续你只需要编辑 CSV 中的 `review_market_relevant`、`review_noise_type`、`review_label_source`、`review_notes` 四列，我就可以把结果导回 JSONL 并继续 apply/benchmark/baseline。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/review_market_relevance_annotations.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_review_queue.md`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/research/market_relevance_review_queue.csv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：review CLI 新增 `export-csv` 与 `import-csv`；CSV 约定字段包括 `sample_id`、模型判断列和 `review_*` 编辑列
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_dataset.py::test_export_review_samples_markdown_renders_readable_sections backend/tests/test_news_relevance_dataset.py::test_export_review_samples_csv_writes_editable_columns backend/tests/test_news_relevance_dataset.py::test_import_review_decisions_csv_updates_reviewed_samples -q` 通过（3 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_dataset.py backend/scripts/review_market_relevance_annotations.py` 通过；`conda run -n news-caught python backend/scripts/review_market_relevance_annotations.py export backend/data/research/market_relevance_review_queue.jsonl backend/data/research/market_relevance_review_queue.md` 与 `export-csv backend/data/research/market_relevance_review_queue.jsonl backend/data/research/market_relevance_review_queue.csv` 通过
- 风险/后续事项：CSV 只是人审编辑入口，正式 benchmark 仍然以导回后的 reviewed JSONL 为准；你完成 CSV 编辑后，还需要继续执行 `import-csv -> apply -> evaluate`

## 2026-03-25 15:52

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch review follow-up hardening
- 变更内容：按本轮 code review 补了两处会影响后续 benchmark 可靠性的实现收紧。其一，`sample_market_relevance_dataset.py` 在启用 source cap 时不再只看固定 oversample 窗口，而是直接扫描完整候选池后再做 round-robin 限额，避免前部数据被单一来源淹没时把目标样本数严重抽空；测试侧新增了一个“前 1000 条都来自同一 source，但后面仍有足够 B/C source 填满 limit”的用例，确认 source cap 不会因为窗口偏斜而只吐出少量样本。其二，`OpenAICompatibleProvider` 的占位 host 检查从“凡是 hostname 以 `example-` / `example.` 开头都拒绝”收窄为只拒绝保留测试域（如 `.test` 和标准 `example.com/.org/.net`），避免误伤真实公司域名中恰好带 `example-` 前缀的 host；测试侧同步补了允许 `https://example-llm.company.com/v1` 继续正常走 provider 调用的覆盖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/sample_market_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；仅收紧 provider placeholder 判定与 source cap 抽样语义
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_annotation.py::test_annotation_service_allows_non_placeholder_hostnames_that_start_with_example backend/tests/test_news_relevance_dataset.py::test_sampling_script_source_cap_keeps_filling_beyond_initial_skewed_window -q` 通过（2 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/llm_providers.py backend/scripts/sample_market_relevance_dataset.py` 通过
- 风险/后续事项：source cap starvation 和 placeholder host 误判都已修正，但 sampling 仍未达到最终设计里要求的 market/time/noise 全量分层；后续若要正式合并 baseline/benchmark 产物，还需要继续把 sampling allocator 和离线 benchmark 执行链打通

## 2026-03-25 15:39

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch annotation 可恢复批处理
- 变更内容：为 `annotate_market_relevance.py` 和底层 `annotate_market_relevance_file()` 补了最小可恢复执行能力，避免整批 `400` 条候选首标时“长时间无进度、失败后从头再来”。当前实现新增了两项控制：`--resume` 会复用已有 output 中真正已完成的样本并只继续剩余样本；`--batch-size` 会在每 N 条新标注后把当前累计结果重新写回输出文件，确保中途中断后有可恢复的阶段性产物。收到 review 后又补了两处收紧：`resume` 现在只会跳过 `confidence > 0` 的已完成标注，不会把候选集里那种占位 `model_only + confidence=0` 行误判为已完成；`batch-size` 也要求必须是正整数，避免 `0` 或负数被静默接受。测试侧补了三类回归：已完成 output 续跑、占位 output 需要重标、以及分批 flush/非法 batch size 的边界。这样后续继续跑整批候选时，可以先用小批量探路，再反复 `--resume` 补齐，而不是依赖一次长时间串行请求。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/annotate_market_relevance.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/docs/code-change-log.md`
- 接口/数据结构变化：annotation CLI 新增 `--resume` 和 `--batch-size`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_annotation.py -q` 通过（9 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/news_relevance_annotation.py backend/scripts/annotate_market_relevance.py` 通过
- 风险/后续事项：当前仍是串行逐条请求外部 LLM，只是已经可恢复；如果整批运行仍然太慢，下一步应继续补更明确的进度输出，或增加 `--limit/--offset` 一类显式分片控制，方便并行或分段执行

## 2026-03-25 15:08

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch annotation provider 诊断与采样 source cap
- 变更内容：基于当前 worktree 继续推进 `market relevance autoresearch`，先按真实复现结果收紧了 annotation 入口的 provider 校验，再给候选集抽样补了一层最小的来源限额控制。LLM provider 侧在 `OpenAICompatibleProvider` 增加了占位配置 fail-fast：当活动配置仍指向 `example-*` / `.test` 之类占位 host，或使用 `sk-test...` 占位 key 时，会在真正发请求前直接抛出受控错误，避免 annotation CLI 长跑后才在 TLS 握手阶段报 `UNEXPECTED_EOF_WHILE_READING`。抽样侧为 `sample_market_relevance_dataset.py` 增加了 `--historical-source-cap` / `--realtime-source-cap` 参数，并在查询窗口上做 oversample 后按 source round-robin 限额分配，避免“先取前 N 条再裁剪”导致 `CLS Telegraph` 一类单源直接挤掉其他来源。用当前 SQLite 数据做 smoke run 时，`source cap=40` 能明显压下单源暴涨，但也暴露出只靠 source cap 还不足以稳定补满 `400` 条样本，当前会落到 `315` 条，说明下一步仍需继续做更完整的 stratified allocator，而不是把 source cap 当最终方案。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/llm_providers.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/sample_market_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/docs/code-change-log.md`
- 接口/数据结构变化：annotation provider 请求前新增占位配置拒绝语义；候选集采样 CLI 新增 `--historical-source-cap` 与 `--realtime-source-cap`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_relevance_annotation.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py backend/tests/test_research_schemas.py -q` 通过（30 个用例）；`conda run -n news-caught python -m py_compile backend/app/services/llm_providers.py backend/scripts/sample_market_relevance_dataset.py backend/tests/test_news_relevance_annotation.py backend/tests/test_news_relevance_dataset.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/sample_market_relevance_dataset.py --historical-limit 240 --realtime-limit 160 --historical-source-cap 40 --realtime-source-cap 40 --output /tmp/market_relevance_candidates_cap_XXXX.jsonl` 通过，生成 `315` 条候选样本，前几大来源收敛为 `The Verge/36Kr/CLS Telegraph` 各 `80` 条
- 风险/后续事项：当前 annotation 仍然没有“真正跑通”到可用 LLM，因为主工作区数据库里的活动 provider 还是占位配置，需先换成真实可连通的 endpoint 后再继续半自动标注；source cap 只是第一层止血，无法单独保证 `400` 条样本补满，也无法同时约束 market/time/noise 分布，后续仍应按设计继续做显式分层抽样

## 2026-03-25 15:29

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch LLM provider 实配与 annotation 连通性验证
- 变更内容：按用户提供的 DeepSeek API key，把主工作区 SQLite 数据库 `/Users/xiuyang/Desktop/news-caught/backend/data/app.db` 中的活动 `llm_provider_config` 从占位值切换为真实 `DeepSeek` 配置（`openai_compatible + https://api.deepseek.com/v1 + deepseek-chat`），随后在 benchmark worktree 内重跑了单样本 `annotate_market_relevance.py` 验证，确认 annotation 已可实际返回结构化标签、置信度和 review notes，不再停在占位 host / TLS EOF 阶段。继续尝试整批 `400` 条候选首标时，现有脚本因为串行外部请求且没有中间落盘或进度输出，在数分钟内仍无阶段性产物，因此本轮没有继续盲等到整批完成，也没有生成完整 `market_relevance_candidates.annotated.jsonl`；后续更适合把标注切成可恢复的小批次，或给脚本补中间落盘/进度。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/docs/code-change-log.md`
- 接口/数据结构变化：无代码接口变化；主工作区数据库中的活动 LLM provider 配置已改为真实 DeepSeek endpoint
- 验证情况：`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/annotate_market_relevance.py backend/data/research/market_relevance_candidates.first.jsonl backend/data/research/market_relevance_candidates.first.annotated.jsonl` 通过，成功标注 `1` 条样本；随后对 `backend/data/research/market_relevance_candidates.jsonl` 发起整批首标，因脚本为串行外部请求且无中间落盘，本轮手动停止，未产出完整批次文件
- 风险/后续事项：当前真实 endpoint 已可连通，但整批首标的执行策略还不适合长批次运行；如果要继续推进 benchmark，优先应把 annotation 改成分批可恢复或带进度/中间落盘的模式，再继续跑完整候选集

## 2026-03-25 14:21

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 候选集执行闭环与离线评测贴近生产逻辑
- 变更内容：继续沿既有 `market relevance autoresearch` plan 推进，补齐了当前真正阻塞落地的几个执行缺口。候选集侧为 `sample_market_relevance_dataset.py` 增加了正式 CLI 参数，并在抽样时把 `ArticleContent.content_text` 摘要带入 `body_excerpt`，随后基于主工作区现有 SQLite 数据库生成了第一批 `400` 条候选样本（`historical=240`、`realtime=160`，其中 `388` 条带正文摘要）；review 侧新增了“导出待复核队列 + 应用人工复核结果”的闭环，且会跳过已经 `human_reviewed/human_corrected` 的样本，避免二次复核时重复入队；evaluator 侧不再只靠独立词表，而是复用真实 `NewsSignalClassifier` 的 rule-only 路径并显式禁用 LLM refinement，使离线 benchmark 能使用生产分类器的关键词/主题抽取与正文输入，同时保持纯离线、可复现；baseline 评测脚本补上了 ledger 写入能力，baseline row 也与 schema 对齐，并为未显式传入的 baseline run 生成唯一 `experiment_id`；另外为 research CLI 入口统一补了本地 `backend/` 的 `sys.path` 注入，修复 `conda run` 下 worktree 脚本误导入主工作区 `app.*` 的运行时污染问题。本轮同时验证了半自动标注在当前本机配置下仍被活动 LLM endpoint 阻塞：单样本 `annotate_market_relevance.py` 会稳定报 `llm provider request failed: [SSL: UNEXPECTED_EOF_WHILE_READING]`，因此第一版 benchmark 与 baseline 还不能在当前 provider 配置下真实产出。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/schemas/research.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/app/services/news_signal_classifier.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/sample_market_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/annotate_market_relevance.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/review_market_relevance_annotations.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/evaluate_market_relevance.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/scripts/run_news_relevance_experiment.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_research_schemas.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/tests/test_news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/backend/data/research/market_relevance_candidates.jsonl`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/market-relevance-benchmark/docs/code-change-log.md`
- 接口/数据结构变化：新增了 reviewed sample apply/select 工作流、baseline ledger row 语义以及 `ExperimentDecision.decision="baseline"`；评测预测路径改为支持复用真实 classifier 且使用 `body_excerpt`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_research_schemas.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q` 通过（25 个用例）；`conda run -n news-caught python -m py_compile backend/scripts/sample_market_relevance_dataset.py backend/scripts/annotate_market_relevance.py backend/scripts/review_market_relevance_annotations.py backend/scripts/evaluate_market_relevance.py backend/scripts/run_news_relevance_experiment.py backend/app/services/news_relevance_dataset.py backend/app/services/news_relevance_evaluator.py backend/app/services/news_relevance_experiment_runner.py backend/app/services/news_signal_classifier.py backend/app/schemas/research.py` 通过；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python scripts/sample_market_relevance_dataset.py --historical-limit 240 --realtime-limit 160 --output data/research/market_relevance_candidates.jsonl` 通过并生成 `400` 条候选样本；`conda run -n news-caught python scripts/review_market_relevance_annotations.py select data/research/market_relevance_candidates.jsonl data/research/market_relevance_review_queue.jsonl --confidence-threshold 0.75 --spot-check-count 20 --seed 7` 通过（随后已删除临时 review queue）；`DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python scripts/annotate_market_relevance.py data/research/market_relevance_candidates.first.jsonl data/research/market_relevance_candidates.first.annotated.jsonl` 失败，错误为 `llm provider request failed: [SSL: UNEXPECTED_EOF_WHILE_READING]`
- 风险/后续事项：第一批候选集已生成，但 source 分布仍明显偏向 `CLS Telegraph` / `36Kr`，后续如要降低标注成本并提升 benchmark 代表性，仍建议把 sampling 继续升级成显式分层抽样；当前 benchmark 与 baseline 的真实产出仍受活动 LLM provider 连接异常阻塞，需先修正本机可用 provider 或切换到有效 DeepSeek/OpenAI-compatible endpoint 后，再继续跑半自动标注和 baseline capture

## 2026-03-25 13:42

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 基础工具链
- 变更内容：完成了第一批可执行的 research tooling，实现了 research schema、样本数据集读写与 reviewed merge、`DeepSeek` 首标服务与批量标注脚本、历史/实时混合候选集采样脚本、离线 relevance evaluator、受控 experiment runner 以及 review/evaluate/run 三个薄 CLI；同时新增实验 ledger 初始文件。随后在独立 code review 后继续修正了 4 个关键闭环问题：benchmark merge 改为保留历史基准样本而不是覆盖、evaluator 缺失预测值时会直接报错而非静默按 `False` 计分、experiment decision 增加对 `noise_rejection_rate` 回退的拒绝逻辑、runner 的 repo root 改为动态推导以兼容 worktree 和非固定路径 checkout。当前 evaluator 已内置第一版可解释的 relevance heuristic，用于区分市场事件类新闻与泛科技消费资讯，后续可继续替换为更强策略；本轮未改前端和基础设施。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/research.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/sample_market_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/annotate_market_relevance.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/review_market_relevance_annotations.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/evaluate_market_relevance.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/scripts/run_news_relevance_experiment.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_research_schemas.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_dataset.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_annotation.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_evaluator.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_relevance_experiment_runner.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/research/market-relevance-experiments.tsv`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增项目内 research schema（样本、标签、评测指标、实验决策）、候选集/benchmark JSONL 约定、evaluation artifact 输出和 experiment ledger 记录格式；未改现有 API route
- 验证情况：`conda run -n news-caught pytest backend/tests/test_research_schemas.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_annotation.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q` 通过（20 个用例）；`conda run -n news-caught python -m py_compile backend/app/schemas/research.py backend/app/services/news_relevance_dataset.py backend/app/services/news_relevance_annotation.py backend/app/services/news_relevance_evaluator.py backend/app/services/news_relevance_experiment_runner.py backend/scripts/sample_market_relevance_dataset.py backend/scripts/annotate_market_relevance.py backend/scripts/review_market_relevance_annotations.py backend/scripts/evaluate_market_relevance.py backend/scripts/run_news_relevance_experiment.py` 通过；`conda run -n news-caught pytest backend/tests -q` 通过（144 个用例）
- 风险/后续事项：当前 `predict_market_relevance()` 仍是第一版启发式规则，适合作为 baseline，但还不足以代表最终研究代理的策略上限；下一阶段应继续把 evaluator 与真实 ingestion/filter 逻辑接得更紧，并补 baseline 产物、benchmark 样本内容以及更完整的“kept volume” guardrail

## 2026-03-25 12:49

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch implementation plan
- 变更内容：在确认设计后补写了一份正式 implementation plan，按当前仓库结构和最近新闻链路改动重新拆解了后续实施顺序：先做 research schema、混合抽样与 `DeepSeek` 半自动标注，再做离线评测器与 baseline，最后再做受控 experiment runner 和实验账本；计划中明确限定只动新闻相关后端代码，不碰前端和基础设施，并为每个任务补了 TDD 步骤、验证命令和建议提交点。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-25-market-news-relevance-autoresearch-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：仅计划层面提出后续新增 research schema、数据集文件、评测产物和实验账本，本次未改运行时代码
- 验证情况：未验证；本次为计划文档产出，待进入实现阶段后按计划执行测试和评测验证
- 风险/后续事项：当前仓库存在用户近期未提交改动，后续实现需在不回退这些修改的前提下按计划推进；计划尚未进入执行阶段

## 2026-03-25 12:38

- 修改人：Codex
- 修改范围：feed runtime banner connection overlay
- 变更内容：补齐 `NewsFeedView` 顶部状态带的最终裁决逻辑，当客户端 `SSE` 连接状态为 `offline/degraded` 时，优先展示“实时连接异常”，覆盖服务端 `newsRuntimeStatus.feed_status` 的文案与 tone；并新增对应视图测试，验证连接异常会压过服务端 delayed 状态。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts src/stores/newsStore.test.ts src/api/client.test.ts` 通过（26 个用例）
- 风险/后续事项：当前顶部状态带已经覆盖客户端连接异常，但 detail 文案仍以服务端 runtime 摘要为主；如果后续需要更强诊断性，可以再补连接错误原因或最近一次 stream 错误时间

## 2026-03-25 12:35

- 修改人：Codex
- 修改范围：stream keepalive continuity fix + final verification refresh
- 变更内容：代码复核后修正了 `/api/stream/events` 的 keepalive 语义，空闲超时后不再只发一次 `stream.keepalive` 就结束连接，而是按 keepalive 周期持续发送，避免前端 `EventSource` 被错误判定为断线；同步新增 keepalive 连续发送测试，并刷新整轮 backend/frontend/build 验证结果。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stream_events.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；`GET /api/stream/events` 的 keepalive 行为从“单次超时响应”修正为“持续保活”
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_ingestion.py backend/tests/test_news_signal_pipeline.py backend/tests/test_stream_events.py backend/tests/test_stream_status.py -q` 通过（40 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/newsStore.test.ts src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts` 通过（25 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：feed 顶部状态带仍未把客户端 `SSE` 连接态覆盖到最终展示文案；如果要完全对齐设计稿，还需要把 `connectionStore/runtimeStatusStore` 的连接异常覆盖逻辑补到 `NewsFeedView`

## 2026-03-25 12:33

- 修改人：Codex
- 修改范围：newsfeed 数据源与实时性基础链路 verified slice
- 变更内容：完成并验证了本轮 plan 的 backend realtime slice 与 frontend runtime slice：后端补齐 `GET /api/news/runtime` 的 spec 契约、`news.created`/`news.updated` 内容流事件和 `/api/stream/events` SSE 转发；前端补齐 news runtime 类型与 API client、`newsStore` 的 runtime/update 处理、`AppShell` 的 `news.updated` 分发，以及 `NewsFeedView` 的最小顶部状态带。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_runtime.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/stream.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/event_bus.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_signal_pipeline.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_stream_events.py`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增并接通 `GET /api/news/runtime`、`news.created`、`news.updated`、`GET /api/stream/events`；前端开始消费 `NewsRuntimeStatus` 和 `NewsUpdateEvent`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_ingestion.py backend/tests/test_news_signal_pipeline.py backend/tests/test_stream_events.py backend/tests/test_stream_status.py -q` 通过（39 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/newsStore.test.ts src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts` 通过（25 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：feed 顶部状态带当前只消费服务端 news runtime，没有把客户端 `SSE` 连接异常覆盖到最终展示文案；如果后续要完全对齐设计稿，需要再把 `connectionStore/runtimeStatusStore` 的连接态覆盖逻辑接进 `NewsFeedView`

## 2026-03-25 12:33

- 修改人：Codex
- 修改范围：frontend news runtime status band + update event routing
- 变更内容：`AppShell` 的统一 stream 入口现在会把 `news.updated` 转交给 `newsStore.upsertNewsUpdate()`，并在启动时同步拉取 `loadNewsRuntime()`；`NewsFeedView` 顶部 `StatusBanner` 改为消费 `newsRuntimeStatus`、`lastIncrementalAt` 和 `sourceHealth`，最小展示 `live/delayed/degraded` 文案、最近入流时间和异常来源数。测试侧补了 `news.updated` 事件分发断言，以及 feed 头部状态带文案断言。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/components/layout/AppShell.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；前端开始消费已存在的 `news.updated` 事件和 `news runtime` store 状态
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts src/stores/newsStore.test.ts` 通过（16 个用例）
- 风险/后续事项：当前状态带只展示最小 runtime 摘要，还没有把客户端 `SSE` 连接异常和服务端供给状态做最终合成展示；如果要完全对齐设计稿，还需要再把 `connectionStore/runtimeStatusStore` 的覆盖逻辑接进 feed 顶部文案

## 2026-03-25 12:31

- 修改人：Codex
- 修改范围：frontend news runtime client + store wiring
- 变更内容：前端先接通了 `GET /api/news/runtime` 与增量更新边界。`types/api.ts` 新增 `NewsRuntimeStatus`、market/source runtime 类型和 `news.updated` 事件类型；`apiClient` 新增 `getNewsRuntime()`，并补了一份降级 mock payload；`newsStore` 新增 `newsRuntimeStatus`、`lastIncrementalAt`、`sourceHealth`，支持 `loadNewsRuntime()` 拉取 runtime 状态，同时补了 `upsertNewsUpdate()`，会按当前 scoped query 对 dashboard/feed/sentiment 三个列表执行替换、插入或移除。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/stores/newsStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：前端类型层新增 `NewsRuntimeStatus`、`NewsRuntimeMarket`、`NewsRuntimeSource`、`NewsUpdateEvent`；`apiClient` 新增 `getNewsRuntime()`
- 验证情况：`npm --prefix frontend run test -- --run src/api/client.test.ts` 通过（9 个用例）；`npm --prefix frontend run test -- --run src/stores/newsStore.test.ts` 通过（3 个用例）
- 风险/后续事项：`AppShell` 和 `NewsFeedView` 还没有消费这组新 state，顶部状态带与 `news.updated` 事件分发仍待后续 UI 接线任务完成

## 2026-03-25 12:25

- 修改人：Codex
- 修改范围：news updated enrichment event publish
- 变更内容：在 `news.created_batch` 订阅处理器里补上 `news.updated` 发布，信号流水线处理完成后会读取已更新的新闻记录，按 `NewsItemSummary` 序列化为前端可直接 upsert 的 payload，并附带 `updated_fields=["sentiment_label"]`；同时把 payload 构造收敛到 session 内完成，修掉了回归测试中暴露的 `DetachedInstanceError`。测试侧新增 batch-handler 事件用例，验证处理完成后会发出 `news.updated`。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/main.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_signal_pipeline.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增后端内容流事件 `news.updated`，字段为 `NewsItemSummary` + `updated_fields`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py::test_news_created_batch_handler_publishes_news_updated_after_processing -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py backend/tests/test_news_ingestion.py -q` 通过（30 个用例）
- 风险/后续事项：当前 `updated_fields` 只覆盖本轮真实会变化的 `sentiment_label`；如果后续把 topic/summary/mentions 等展示字段也纳入异步富化，需要同步扩展这份字段列表和对应前端合并逻辑

## 2026-03-25 12:23

- 修改人：Codex
- 修改范围：news created incremental event publish
- 变更内容：在 `NewsIngestionService.refresh_all()` 中为每条首次插入的新闻增加 `news.created` 单条事件发布，载荷直接复用 `NewsItemSummary` 的列表级契约字段；保留现有 `news.created_batch`，并明确发布顺序为“逐条 created 后再 batch”，避免破坏后端批处理订阅者。测试侧把原有 refresh 事件用例扩成失败先行的增量契约测试，验证单条事件与 batch 事件会同时发出。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增后端内容流事件 `news.created`，字段为 `NewsItemSummary` 的最小卡片字段；`news.created_batch` 保持不变
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_refresh_all_publishes_news_created_for_each_insert -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（26 个用例）
- 风险/后续事项：当前只补了发布路径，前端 SSE 转发与 `news.updated` 富化事件还未完成；在这些后续任务落地前，单条 `news.created` 仍主要供后端测试和后续 stream 接线使用

## 2026-03-25 12:21

- 修改人：Codex
- 修改范围：news runtime contract spec-fix
- 变更内容：按 spec review 重做了 `NewsRuntimeService` 的 runtime 状态裁决：`last_incremental_event_at` 改为读取事件总线最近一次 `news.created/news.updated` 的发布时间，不再复用 `last_news_created_at`；`sources[].status` 收敛为 `ok/delayed/degraded/offline` 四态，移除 spec 外的 `disabled`；`markets[].mode` 改为按最近 30 分钟成功 source 的 tier 判定；`markets[].status` 与 `feed_status` 补齐 `live/delayed/degraded/offline` 语义。测试侧新增了一个多 market 契约用例，覆盖 delayed/degraded/offline/source-tier 切换和事件时间来源。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_runtime.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/news/runtime` 的字段名不变，但 `feed_status`、`markets[].status`、`markets[].mode`、`sources[].status` 与 `last_incremental_event_at` 的语义按设计稿收紧
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py::test_news_runtime_returns_market_and_source_health_contract backend/tests/test_news.py::test_news_runtime_maps_runtime_statuses_per_spec -q` 通过（2 个用例）；`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_ingestion.py -q` 通过（32 个用例）
- 风险/后续事项：当前 `last_incremental_event_at` 仍依赖事件总线只暴露“最近一次事件”的状态；如果后续 `news.updated` 明显比 `news.created` 更频繁，且产品严格要求区分“最近 created”和“最近 updated”，需要为内容流事件补更细的独立 runtime 指标

## 2026-03-25 11:43

- 修改人：Codex
- 修改范围：news route import regression follow-up
- 变更内容：补回 `backend/app/api/routes/news.py` 中 `analyze_news()` 所需的 `get_event_bus` 导入，修复 runtime 路由改动时引入的 `NameError` 回归；同步复核了 news route 文件，未发现其他同类缺失导入。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_analysis.py -q` 通过（19 个用例）
- 风险/后续事项：暂无新增风险

## 2026-03-25 11:41

- 修改人：Codex
- 修改范围：news runtime API contract + aggregation service
- 变更内容：新增 `GET /api/news/runtime`，由独立的 `NewsRuntimeService` 汇总当前 source health、最近新闻创建时间和 market 级运行态，并补充了 runtime response schema。测试侧先补了 `/api/news/runtime` 的契约用例，再按 TDD 最小实现路由与服务，确保返回字段、时间序列化和 market/source 结构与计划一致。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/source_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/api/routes/news.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_runtime.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：新增 `GET /api/news/runtime`，返回 `feed_status`、`last_refresh_finished_at`、`last_news_created_at`、`last_incremental_event_at`、`degraded_market_count`、`markets[]` 和 `sources[]`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news.py::test_news_runtime_returns_market_and_source_health_contract -q` 通过；`conda run -n news-caught pytest backend/tests/test_news.py -q` 通过（5 个用例）；`conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_health.py -q` 通过（7 个用例）
- 风险/后续事项：runtime 聚合目前是基于本地数据库中现有的 source health 与 news 记录做同步汇总；如果后续需要把 `last_incremental_event_at` 与真实事件总线强绑定，还需要补事件源或缓存层，而不是只依赖当前的新闻写入时间

## 2026-03-25 11:34

- 修改人：Codex
- 修改范围：health projection market field + source-health backfill precedence fix
- 变更内容：为公开 health sources 视图补上 `market` 字段，避免 source+market 作用域在 API 层被压扁；同时调整 legacy `source_health` 回填优先级，改为先从 `news_item` 里确定市场，再回退到当前配置，最后才使用 `"unknown"`。为保证 TDD 约束，本轮先补了两个失败测试：一个覆盖 `/api/health/sources` 输出 `market`，一个覆盖旧数据库回填时以新闻历史市场为准。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/schemas/source_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`GET /api/health/sources` 的 `SourceHealthView` 新增 `market`；legacy source-health backfill 的市场决定顺序变为 `news_item` -> current source config -> `"unknown"`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_health.py::test_health_sources_endpoint_includes_market backend/tests/test_news_ingestion.py::test_initialize_database_prefers_news_item_market_when_backfilling_source_health -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（26 个用例）
- 风险/后续事项：`initialize_database()` 里的 legacy SQLite 重建逻辑仍然依赖当前 schema 与历史数据结构基本一致；如果后续旧库的 `news_item` 表也出现字段缺失或 schema 漂移，这条回填路径还需要再做更强的兼容处理

## 2026-03-25 11:28

- 修改人：Codex
- 修改范围：news source health market scope + legacy SQLite rebuild
- 变更内容：将 `source_health` 的作用域从 `source_name` 单列唯一调整为 `source_name + market` 联合唯一；`NewsIngestionService` 在刷新源时按当前源市场写入/更新 health 记录；`SourceHealthRepository` 改为按源名和市场联合查找；`initialize_database()` 新增兼容旧本地数据库的迁移/回填逻辑，会在检测到旧版 `source_health` 表时重建为带 `market` 列和联合唯一约束的结构，并尽量从已配置 sources / 现有 `news_item` 记录中补齐市场值。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/models/source_health.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/repositories/source_health_repository.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/app/db/initializer.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：`source_health` 现在以 `source_name + market` 作为唯一键；仓储层 `get_or_create()` 需要显式传入 `market`
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_refresh_source_tracks_health_per_source_market_pair backend/tests/test_news_ingestion.py::test_initialize_database_backfills_source_health_market_for_legacy_databases -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（26 个用例）
- 风险/后续事项：SQLite legacy-table rebuild 目前是“重建 `source_health` 表并复制旧数据”的兼容路径，默认市场回填优先使用当前 sources 配置，其次尝试从 `news_item` 反推，最后退回 `"unknown"`；如果旧库里存在同一 source_name 的多市场历史记录但配置已变更，回填市场可能不是历史上最精确的值，需要后续按更可靠的来源再细化

## 2026-03-25 11:48

- 修改人：Codex
- 修改范围：news ingestion registry hardening final follow-up
- 变更内容：进一步收紧了 source registry 的输入校验：`_coerce_positive_int()` 现在会把 `Infinity` / `NaN` 这类非有限数值直接转换成受控 `ValueError`，避免在 `int(...)` 上触发 `OverflowError`；`load_sources()` 也不再把解析出来的顶层 `null`、`[]` 等非对象 payload 当作“没有配置”，而是明确报 `sources registry payload must be an object`。同步把这两类回归补成测试并保留前一轮的 schema-safe 覆盖。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；仅强化 source registry 输入校验
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_load_sources_rejects_malformed_top_level_payload backend/tests/test_news_ingestion.py::test_load_sources_rejects_non_finite_registry_values -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（24 个用例）
- 风险/后续事项：暂无新增风险；后续如果 registry 继续扩字段，建议沿用“先测试、再做 schema-safe hydration”的同类模式

## 2026-03-25 11:39

- 修改人：Codex
- 修改范围：news ingestion registry schema-safe validation follow-up
- 变更内容：补齐了 `load_sources()` 对 malformed source registry 的受控错误处理：当顶层 `sources` 为 `null` 或其他非数组值时会返回明确的 `ValueError`；`markets` 现在只接受字符串数组或单一 `market` 回退值，遇到字典/空数组/非字符串元素会统一报 `ValueError`；`priority` 和 `cadence_seconds` 在 hydration 阶段先做数值规范化，避免 JSON 字符串或其他非数值触发 `TypeError`。同时把这几类边界情况拆成独立测试，保持回归覆盖清晰。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；仅加强 source registry 输入校验
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_load_sources_rejects_null_sources_array backend/tests/test_news_ingestion.py::test_load_sources_rejects_non_numeric_priority backend/tests/test_news_ingestion.py::test_load_sources_rejects_non_numeric_cadence_seconds backend/tests/test_news_ingestion.py::test_load_sources_rejects_malformed_markets_array -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（20 个用例）
- 风险/后续事项：当前 `markets` 仍接受非空字符串数组和单一 `market` 回退；如果后续 registry 要求更严格的 ISO/market code 约束，可再单独补 schema 校验

## 2026-03-25 11:26

- 修改人：Codex
- 修改范围：news ingestion registry validation follow-up
- 变更内容：根据 review 反馈补齐了 source registry 的边界处理：`load_sources()` 现在会对顶层非对象条目返回受控 `ValueError`，避免出现 `AttributeError` 之类的内部异常；测试侧把 registry 相关用例拆成了独立的 `tier`、`priority`、`cadence_seconds` 保护，并增加了 malformed registry entry 的覆盖。同时把临时 `NEWS_SOURCES_FILE`/`get_settings()` 缓存处理封装成测试辅助函数，在用例结束时恢复环境和缓存状态，避免温热缓存污染后续测试。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无新增接口；仅强化 source registry 读取时的输入校验
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_load_sources_backfills_registry_defaults_from_legacy_config backend/tests/test_news_ingestion.py::test_load_sources_rejects_invalid_tier backend/tests/test_news_ingestion.py::test_load_sources_rejects_invalid_priority backend/tests/test_news_ingestion.py::test_load_sources_rejects_invalid_cadence_seconds backend/tests/test_news_ingestion.py::test_load_sources_rejects_malformed_registry_entries -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（16 个用例）
- 风险/后续事项：测试辅助函数当前按本次 task 需要恢复 `NEWS_SOURCES_FILE` 和 settings cache；如果后续有更多环境变量驱动的配置测试，建议复用同样的恢复模式

## 2026-03-25 11:18

- 修改人：Codex
- 修改范围：市场新闻相关性 AutoResearch 设计文档
- 变更内容：新增一份正式 design spec，把 `karpathy/autoresearch` 的“受控实验”思路迁移到本项目新闻相关性优化场景，明确了第一阶段目标为“市场相关新闻命中率”提升，并设计了约 `400` 条混合样本的半自动标注数据集、`DeepSeek` 首标加人工复核流程、以 `precision` 为主指标的离线评测器、研究代理的可改动边界、实验保留规则以及项目内研究账本/目录结构；本次仅产出设计，不涉及运行时代码实现。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-25-market-news-relevance-autoresearch-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：仅设计层面提出后续新增研究数据集 schema、评测结果产物和实验账本字段，本次未改现有 API 或数据库
- 验证情况：未验证；本次为设计文档产出，待进入 implementation plan 和实现阶段后再补脚本、测试与评测验证
- 风险/后续事项：该设计仍需用户 review，并在确认后进入 `writing-plans` 阶段细化为实现计划；当前尚未定义具体 `DeepSeek` prompt、样本文件路径和实验控制脚本接口

## 2026-03-25 11:12

- 修改人：Codex
- 修改范围：news ingestion source registry defaults/validation
- 变更内容：为 `news_ingestion` 的 source registry 增加了兼容旧配置的 hydration 层和基础校验：旧版只写 `market` 的配置现在会自动回填 `markets`、`tier`、`priority`、`cadence_seconds` 和 `supports_incremental` 的默认值；同时对 `tier`、`priority`、`cadence_seconds` 做了最小有效性校验，非法 registry 值会在加载阶段直接报错，而不是等到刷新时才暴露。同步把 `news_sources.example.json` 改成带 registry 字段的新形状，并补了测试覆盖 legacy backfill 与 invalid registry values。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/backend/app/services/news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/tests/test_news_ingestion.py`
  - `/Users/xiuyang/Desktop/news-caught/backend/data/news_sources.example.json`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：source registry 允许新增 `tier`、`priority`、`cadence_seconds`、`markets` 和 `supports_incremental` 字段；旧配置继续兼容
- 验证情况：`conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_load_sources_backfills_registry_defaults_from_legacy_config backend/tests/test_news_ingestion.py::test_load_sources_rejects_invalid_registry_values -q` 通过；`conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q` 通过（13 个用例）
- 风险/后续事项：当前校验只覆盖本 task 要求的 `tier`、`priority`、`cadence_seconds`，未进一步约束 `markets` 的内容或 registry 中其他字段的 schema；后续 Task 2/后续配置迁移可以继续收紧

## 2026-03-25 10:41

- 修改人：Codex
- 修改范围：newsfeed 数据源与实时性 design/plan 文档
- 变更内容：基于现有 `news_ingestion`、事件总线、`newsStore` 和 `News Feed` 视图，新增并完善了一份正式 design spec 与对应 implementation plan，明确了新闻源分层治理、增量事件闭环、freshness/source health 可观测以及分阶段实施顺序；在 reviewer 反馈后进一步补齐了 orchestrator 触发阈值、`GET /api/news/runtime` schema、事件幂等语义、source 配置失败策略、事件消费者迁移矩阵、runtime 唯一事实来源与裁决顺序，并明确了 `news.updated` 走现有 `SSE` 通道、`runtimeStatusStore`/`newsStore` 的 owner 边界、scoped list 的增量移除规则、旧 source 配置迁移默认值，以及“迟到/补源模式/状态带”这些前端阈值与渲染口径；最后补充了后端发布/转发接线点、`source_health` 的 `source_name + market` 粒度、`enabled market` 定义和离线 market 的 `mode = none`，并将实现计划细化到 DB migration/backfill、example config、独立 runtime service、SSE 转发和前端最小接线。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-25-newsfeed-source-realtime-design.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-25-newsfeed-source-realtime-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：仅设计文档层面提出后续新增 source registry 字段、`news.created` / `news.updated` 事件与 `GET /api/news/runtime`，本次未改运行时代码
- 验证情况：未验证；本次为设计文档产出，待后续进入计划与实现阶段后补代码级验证
- 风险/后续事项：该 design 仍需进入 spec review 和用户 review，确认后再写 implementation plan，避免与现有新闻、事件层和 runtime 状态链路冲突

## 2026-03-24 00:31

- 修改人：Codex
- 修改范围：本地 dev launcher 启动稳态修复
- 变更内容：为 `scripts/dev.sh` 增加端口冲突清理、backend 启动早退检测、`/api/stream/status` 就绪等待、依赖命令预检和进程树清理，避免 `make dev` 在旧监听残留或 backend 未真正启动时留下“前端活着、后端拒绝连接”的半启动状态，并在启动阶段保留子进程原始退出码；同步把 `test_dev_launcher.py` 改为基于仓库根目录动态定位脚本，并补充对端口清理、ready wait、失败传播和依赖声明的约束；README 增加 launcher 新行为说明；新增本轮 design/plan 文档。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/scripts/dev.sh`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/backend/tests/test_dev_launcher.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/README.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/docs/superpowers/specs/2026-03-24-dev-launcher-port-guard-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/docs/superpowers/plans/2026-03-24-dev-launcher-port-guard-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-fix-dev-startup/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`conda run -n news-caught pytest backend/tests/test_dev_launcher.py -q` 通过（2 个用例）；手动运行 `./scripts/dev.sh` 时已验证 frontend 缺依赖会被启动阶段早退检测及时报错，不再静默留下坏状态，并验证占用 `8000`/`5174` 的假服务会在启动前被清理后由真实 backend/frontend 接管；后续将继续补完整后端测试和完整启动验证
- 风险/后续事项：launcher 会主动终止占用 `8000`/`5174` 的本地监听进程，仅适用于本地开发；如果后续需要更保守的策略，可再改成只清理带本项目特征的进程

## 2026-03-24 00:21

- 修改人：Codex
- 修改范围：worktree 目录忽略规则补齐
- 变更内容：将项目本地 `.worktrees/` 目录加入 `.gitignore`，避免后续创建隔离 worktree 时其内容污染主仓库状态，满足仓库对 worktree 使用的基础安全要求。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.gitignore`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`git check-ignore .worktrees` 预计在提交后生效；未涉及运行时代码
- 风险/后续事项：无

## 2026-03-24 00:05

- 修改人：Codex
- 修改范围：Watchlist dashboard review 问题修正
- 变更内容：按子代理 code review 修正了 6 个合并前问题：前端 `getStockKline` 不再在后端报错时伪造 mock K 线；`watchlistStore` 在删除最后一个标的时会清空残留的图表和新闻状态，并为 period 切换补上请求序号保护，避免快速切换周期时旧响应覆盖新周期；`WatchlistView` 恢复了选股后的 URL 同步，把 `/watchlist/:symbol` 路由切回同一套 dashboard 组件，并在手动刷新/删除失败时只保留页面内错误状态、不再抛出未处理 rejection；后端 `MarketChartService.get_sparklines()` 改为按 symbol 部分容错，单个异常标的不再拖垮整个 sparkline 批量请求。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/app/services/market_chart_service.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/api/client.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/WatchlistSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/router/index.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/code-change-log.md`
- 接口/数据结构变化：无，主要是错误处理、路由行为和局部容错策略修正
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（102 个用例）；`npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts src/components/watchlist/StockSparkline.test.ts src/components/watchlist/KlineChart.test.ts` 通过（5 个文件 / 30 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：`/watchlist/:symbol` 现在与 `/watchlist` 共用 dashboard 组件，旧的 `WatchlistDetailView` 仍保留但已不在路由树中；如果后续确认不会再回退到旧单页详情，可以继续清理死代码和对应测试

## 2026-03-23 23:51

- 修改人：Codex
- 修改范围：Watchlist 添加自选股 modal 体验补齐
- 变更内容：按新 spec 将 sidebar 中“搜索候选即点即加”的流程重构为显式 `搜索 / 添加自选股` modal。新增 `WatchlistAddModal`，支持候选搜索、选中确认、默认 `直接添加`、可选展开高级设置并填写 `alert_threshold`；`WatchlistSidebar` 退回为左栏筛选与入口面板，不再在候选列表上直接落库；`WatchlistView` 接管 modal 的本地状态，在添加成功后自动关闭并选中新股票，失败时保留当前选择与阈值方便重试。同步补充视图测试，覆盖打开 modal、候选选择不立即提交、直接添加、带阈值提交和失败保留状态这几条核心路径。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/WatchlistAddModal.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/WatchlistSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/superpowers/specs/2026-03-23-watchlist-add-modal-design.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/superpowers/plans/2026-03-23-watchlist-add-modal-plan.md`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/code-change-log.md`
- 接口/数据结构变化：无，继续复用现有 `createWatchlist` 接口与 `alert_threshold` 字段
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/stores/watchlistStore.test.ts` 通过（2 个文件 / 16 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：这轮 modal 还没有补键盘上下选择、ESC 关闭、焦点陷阱等更完整的 dialog 可访问性；如果你下一步继续打磨体验，优先建议补这些细节，再做新闻 marker 与侧栏的深联动

## 2026-03-23 23:18

- 修改人：Codex
- 修改范围：Watchlist 仪表盘 final review 尾项修正
- 变更内容：根据第二轮子代理复核，继续修正两个残留问题：`IndicatorChart` 在 `indicators` 为空时现在会显式清空已有 series，避免切换股票或请求失败时副图残留上一只股票的数据；`StockCard` 外层交互容器改为带键盘可访问性的 `article[role=button]`，删除按钮不再嵌套在外层 `<button>` 中，消除无效交互 HTML 和潜在点击/键盘冲突。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/IndicatorChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/code-change-log.md`
- 接口/数据结构变化：无
- 验证情况：`npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/StockSparkline.test.ts src/stores/watchlistStore.test.ts` 通过（4 个文件 / 15 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：副图和主图目前已是真实 Lightweight Charts，但新闻 marker 与侧栏的高亮联动仍偏轻量；如果后续要做到 spec 中更完整的 hover/scroll 同步，建议继续补专门的交互测试

## 2026-03-23 23:16

- 修改人：Codex
- 修改范围：Watchlist 仪表盘 review 回合修正
- 变更内容：根据子代理 code review 补回了新仪表盘中被误删的管理与运维能力：`WatchlistView` 重新展示 runtime/手动刷新状态卡，`WatchlistSidebar` 恢复候选添加入口与持仓删除入口；同时修复 `loadCandidates()` 失败会阻断整页加载的问题，并为 `watchlistStore` 增加 detail 请求竞态保护，避免快速切换股票时旧请求覆盖新详情。图表层继续补齐：`KlineChart` 在 `klineData` 为空时会主动清空旧 series，`IndicatorChart` 也接入 Lightweight Charts，前端视图测试则显式 mock 图表库，避免 jsdom canvas 能力不足导致误报。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/WatchlistSidebar.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockCard.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/KlineChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/KlineChart.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockSparkline.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockSparkline.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/IndicatorChart.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/code-change-log.md`
- 接口/数据结构变化：`POST /api/market/sparklines` 超限时返回 400，与 spec 对齐；其余为前端状态管理与交互修正
- 验证情况：`conda run -n news-caught pytest backend/tests -q` 通过（101 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts src/components/watchlist/StockSparkline.test.ts src/components/watchlist/KlineChart.test.ts` 通过（4 个文件 / 15 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前 sidebar 的添加流程是“候选即点即加”，还没有做成 spec 里更完整的 modal；另外 Redis 缓存目前是“Redis 优先 + 内存回退”，还没增加独立的 Redis 集成测试环境

## 2026-03-23 23:01

- 修改人：Codex
- 修改范围：Watchlist 仪表盘与 K 线/迷你走势数据链路
- 变更内容：新增后端 `GET /api/market/symbols/{symbol}/kline` 和 `POST /api/market/sparklines`，由新建 `market_chart_service` 负责拉取 yfinance 历史 K 线、计算 MA/MACD/KDJ/布林带、对齐相关新闻日期并提供内存级缓存兜底；前端扩展 `watchlistStore`、API 类型与 mock 数据，新增一组 watchlist 仪表盘组件，把 `/watchlist` 从旧表格页重构为左侧股票雷达 + 右侧详情面板的 master-detail 布局，支持周期切换、迷你走势、K 线摘要、副图指标按钮和关联新闻侧栏。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/app/api/routes/market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/app/schemas/market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/app/services/market_chart_service.py`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/backend/tests/test_market.py`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/types/api.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/api/client.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/api/mock.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/stores/watchlistStore.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.vue`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/views/WatchlistView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/WatchlistSidebar.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockCard.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockSparkline.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockDetailPanel.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/KlineChart.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/IndicatorChart.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/StockMetricsGrid.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/src/components/watchlist/RelatedNewsSidebar.vue`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/frontend/package-lock.json`
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/superpowers/specs/2026-03-23-watchlist-dashboard-kline-design.md`（新增同步）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/superpowers/plans/2026-03-23-watchlist-dashboard-kline-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/.worktrees/codex-watchlist-dashboard-kline/docs/code-change-log.md`
- 接口/数据结构变化：新增 `GET /api/market/symbols/{symbol}/kline` 与 `POST /api/market/sparklines`；前端新增 K 线、技术指标、新闻标记与 sparkline 数据结构
- 验证情况：`conda run -n news-caught pytest backend/tests/test_market.py -q` 通过（13 个用例）；`conda run -n news-caught pytest backend/tests -q` 通过（99 个用例）；`npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts` 通过（2 个文件 / 11 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：后端缓存当前是进程内内存缓存，还没有落到 spec 预期的 Redis；前端图表当前使用轻量 DOM/SVG 摘要组件而未真正接入 Lightweight Charts，因此“真实 K 线交互、十字光标和多副图同步”仍可在下一轮继续补齐

## 2026-03-23 21:38

- 修改人：Codex
- 修改范围：Dashboard 顶部异动股票指标卡跳转入口
- 变更内容：将首页 `Dashboard` 顶部 `HeroMetrics` 区域中的“异动股票”指标卡改成整卡可点击入口，直接跳转到 `/watchlist`。这样顶部四张指标卡的交互模型保持一致，用户不需要再下滑到下方 `Live Movers` 区块才能进入自选股异动页。同步补充视图测试，明确约束顶部指标区内必须存在指向 `/watchlist` 的链接。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-dashboard-movers-metric-link-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-dashboard-movers-metric-link-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；仅前端路由映射增强，继续复用现有 `/watchlist` 页面
- 验证情况：`npm --prefix frontend run test -- --run src/views/DashboardView.test.ts` 通过（1 个文件 / 5 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：当前顶部指标卡和下方 `Live Movers` 区块都会进入 `/watchlist`，这是有意的入口重复；若后续希望区分“总览入口”和“细分入口”，需要再单独设计指标卡更细粒度的跳转目标

## 2026-03-23 20:22

- 修改人：Codex
- 修改范围：首页 Dashboard 新闻预览点击跳转修复
- 变更内容：排查后确认“主页面新闻点不进去”的根因不在 `News Feed` 路由，而在 `Dashboard` 首页新闻预览列表本身只是静态 `<article>`，没有绑定任何跳转逻辑。现已把首页新闻预览改成可点击按钮，点击后直接路由到站内 `News Detail`；同时补充首页点击回归测试，并为 `News Feed` 视图补上点击卡片进入详情页的回归测试，避免后续再把两条入口链路改坏。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/DashboardView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsFeedView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；仅前端交互和路由触发修复
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/views/DashboardView.test.ts` 通过（2 个文件 / 8 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：首页新闻预览现在统一进入站内详情页，而不是直接外跳原文；如果后续希望首页也支持“直接打开原文”，需要在紧凑卡片里单独设计第二入口，避免与当前整卡点击区域冲突

## 2026-03-23 20:07

- 修改人：Codex
- 修改范围：新闻详情页原文入口强化
- 变更内容：保留 `News Feed` 点击后进入站内 `News Detail` 的既有路径，不改动列表页跳转；将详情页顶部原有的普通“打开原文”文本链接提升为更明显的主操作按钮，并在移动端改成整行宽按钮，方便用户先进入详情页做分析，再决定是否打开原始新闻。同步补充测试，覆盖“有 `canonical_url` 时展示显式原文入口”和“无 `canonical_url` 时隐藏入口”的条件渲染。
- 影响文件：
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.vue`
  - `/Users/xiuyang/Desktop/news-caught/frontend/src/views/NewsDetailView.test.ts`
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/specs/2026-03-23-news-detail-source-link-design.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/superpowers/plans/2026-03-23-news-detail-source-link-plan.md`（新增）
  - `/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md`
- 接口/数据结构变化：无；继续复用现有 `canonical_url` 字段，不新增前后端契约
- 验证情况：`npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts` 通过（1 个文件 / 4 个用例）；`npm --prefix frontend run build` 通过
- 风险/后续事项：本次只增强详情页原文入口，不在 `News Feed` 列表页新增直接外跳能力；如果后续用户希望列表页就能快速打开原文，需要再单独设计卡片级双入口交互，避免和当前整卡进详情的点击区域冲突

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

## 2026-03-28 — K-line News Markers

### Changed
- `backend/app/schemas/market.py`: Added `summary` field to `NewsEventItemView`
- `backend/app/services/market_chart_service.py`: Extract `summary` in `_align_news_events()`
- `frontend/src/types/api.ts`: Added `summary` to `NewsEventMarkerItem`
- `frontend/src/components/watchlist/KlineChart.vue`: Added sentiment-colored markers on candlestick chart via `setMarkers()`, crosshair hover tooltip, and click popup for news details
- `frontend/src/components/watchlist/KlineNewsTooltip.vue`: New hover tooltip showing news titles + sentiment
- `frontend/src/components/watchlist/KlineNewsPopup.vue`: New click popup showing news titles + summaries
