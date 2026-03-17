# 代码变更记录

> 用于记录本项目每一次实际修改。新增记录时，追加到最上方。

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
