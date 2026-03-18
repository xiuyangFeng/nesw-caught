# 代码变更记录

> 用于记录本项目每一次实际修改。新增记录时，追加到最上方。

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
