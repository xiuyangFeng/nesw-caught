# 市场总览（Market Overview）实现计划

日期：2026-08-02
分支：feature/market-overview
设计文档：`docs/superpowers/specs/2026-08-02-market-overview-design.md`（开放问题已定案，见设计文档十三节）
状态：待实施

## 实施总则

- 遵循 TDD：每个任务先写能描述新行为的失败测试，再写生产代码，测试转绿后才算完成。
- 每个任务完成后立即在 `docs/code-change-log.md` 追加一条记录（格式见 AGENTS.md 二节）。
- 后端改动最小验证：`conda run -n news-caught pytest backend/tests` 相关用例；收尾阶段跑全量。
- 前端改动最小验证：`npm --prefix frontend run build`；单测用项目既有命令 `npm --prefix frontend test -- --run`（可加文件名过滤跑目标用例）。
- 不改路由、不动 `AppShell.vue`、不改现有 `MarketQuoteProducer` 行为；除联调节点外不做 git 提交。

## 依赖关系总览

```
后端线：B1 ─┬→ B3 ─→ B6 ─┐
           ├→ B6         ├→ B7（worker 接线）
           B2 ────────→ B7
           B4 ─→ B6
           B5 ─→ B6
前端线（以后端契约为准，走 mock 并行开发）：
           F1 → F2 → F3 → F4 → F5
联调：      C1（依赖 B6、B7、F5）
```

- B1（配置表）是 B3/B6 的前置；B4/B5 互不依赖，可在 B3 之后并行；B6 依赖 B1+B3+B4+B5；B7 依赖 B2+B3（聚合端点非前置，但建议 B6 完成后统一验收）。
- 前端线 F1–F5 只依赖设计文档中的 `/api/market/overview` 契约与 mock，**可与整条后端线并行**；C1 联调必须等 B6+B7+F5 全部完成。

## 后端线任务

### B1 — `market_index_config` 数据模型、Alembic 迁移与 Repository

- 改动文件：
  - 新增 `backend/app/models/market_index_config.py`（字段：id/symbol/market/display_name/kind/sort_order/enabled/时间戳，`UniqueConstraint("symbol","market")`，`(market, enabled, sort_order)` 索引；复用 `TimestampMixin`）
  - 新增 `backend/alembic/versions/<rev>_add_market_index_config.py`（upgrade 建表+索引，downgrade 删表；不 seed 数据）
  - 新增 `backend/app/repositories/market_overview_repository.py`（list_all / list_enabled / get / create / update / delete，按 (market, sort_order) 排序）
  - 顺带确认 data_cleanup 对 `price_snapshot` 的清理覆盖指数 symbol（设计文档十三.3 定案事项；若不覆盖，在本任务内补上并在 change log 记录）
- 先写的失败测试：`backend/tests/test_market_index_config_repository.py`
  - 建表后 CRUD 全链路；同 (symbol, market) 重复 create 抛 IntegrityError；list_enabled 只回 enabled 且按 sort_order 排序；update 不允许改 symbol/market（repository 层无该入口）。
- 验收命令：
  - `conda run -n news-caught pytest backend/tests/test_market_index_config_repository.py`
  - 临时 SQLite 上 `conda run -n news-caught alembic upgrade head` 再 `downgrade -1` 再 `upgrade head`，确认迁移可逆（用 `ALEMBIC_DATABASE_URL` 或临时副本，不污染 `backend/data` 本地库）。

### B2 — 配置项与 `market_hours` 交易时段扩展

- 改动文件：
  - `backend/app/core/config.py`：新增 `market_overview_producer_enabled`(True) / `market_overview_poll_interval_seconds`(60.0) / `market_overview_idle_poll_interval_seconds`(300.0) / `market_board_cache_ttl_seconds`(60) / `market_overview_news_lookback_hours`(24)
  - `backend/app/services/market_hours.py`：新增 `_OVERVIEW_SESSIONS_UTC`（kr 00:00-06:30、jp 00:00-06:00、eu 07:30-16:30 UTC，cn/hk/us 复用现有时段）+ `any_overview_market_open(now=None)`；**不改** `_SESSIONS_UTC` 与 `is_market_open`/`any_market_open` 语义
- 先写的失败测试：`backend/tests/test_market_hours.py` 增补
  - `any_overview_market_open` 在各市场盘中/闭市/周末边界 UTC 时刻的断言；既有 cn/hk/us 用例保持全绿（回归）。
- 验收命令：`conda run -n news-caught pytest backend/tests/test_market_hours.py`

### B3 — MarketOverviewService：指数报价刷新与量化情绪

- 改动文件：
  - 新增 `backend/app/services/market_overview_service.py`：
    - `refresh_index_quotes(session)`：读配置表（空则用内置默认清单，含 ^VIX 与 kind=etf 条目，清单常量为模块级）→ 直接构造 `NormalizedSymbol(symbol=原始ticker, market=配置market, provider_symbol=原始ticker)` → `YahooFinanceQuoteProvider.fetch_quotes_batch` → 网络完成后单次写事务 `MarketRepository.save_snapshot` 批量 flush + commit（两阶段纪律）
    - `list_index_quotes(session)`：配置表 join `price_snapshot` 最新快照（复用 `MarketRepository.list_latest_by_symbols`）
  - 新增 `backend/app/services/market_sentiment_service.py`：`compute_market_sentiment(indices, vix, board_stats)` 纯函数（设计文档七节规则：指数动量 0.6 / VIX 0.25 仅 us / 涨跌家数 0.15 仅 cn，缺输入重归一权重，全缺返回 unknown；`^VIX` 常量在 us 市场指数中提取 VIX 值且不进行列表）
- 先写的失败测试：
  - `backend/tests/test_market_overview_service.py`：mock provider，断言"先联网后写库"（写事务内无网络调用）、批量落库行数、配置表为空时回落默认清单、provider 失败行不回写、cn 指数不被路由到腾讯源（直接调 Yahoo provider）。
  - `backend/tests/test_market_sentiment_service.py`（量化部分）：各分段阈值边界、VIX 缺失时权重让渡、涨跌家数缺失、全缺返回 `label="unknown"`、恐慌/贪婪极端值。
- 验收命令：`conda run -n news-caught pytest backend/tests/test_market_overview_service.py backend/tests/test_market_sentiment_service.py`
- 依赖：B1。

### B4 — EastMoneyBoardProvider 与板块缓存

- 改动文件：
  - 新增 `backend/app/services/board_provider.py`：`BoardQuote` dataclass（code/name/price/change_percent/advance_count/decline_count/flat_count/net_inflow/fetched_at）+ `EastMoneyBoardProvider.fetch_industry_boards(limit=20)`（push2 clist 接口，`fs=m:90+t:2`，fields f12/f14/f2/f3/f104/f105/f106/f62；复用 `http_pool.get_feed_client()`，Referer 头，5s 超时，防御性解析）+ 模块级 TTL 缓存（Lock + cached_at，TTL 走 `market_board_cache_ttl_seconds`；失败返回旧缓存并标 stale，无缓存返回空+fetch_failed）+ 测试用 `clear_board_cache()`
- 先写的失败测试：`backend/tests/test_board_provider.py`
  - mock httpx：正常解析字段映射、f104/f105/f106 聚合、data/diff 缺失容错、HTTP 异常降级到旧缓存（stale=True）、无缓存时 fetch_failed、TTL 内不重复请求。
- 验收命令：`conda run -n news-caught pytest backend/tests/test_board_provider.py`
- 依赖：B2（配置项）。可与 B3/B5 并行。

### B5 — 新闻情绪按市场聚合

- 改动文件：
  - `backend/app/services/market_sentiment_service.py` 增补：
    - 归属映射 `_NEWS_MARKET_MAP = {us→us, cn→cn, hk→cn, kr→kr, jp→jp, eu→eu}`；三级归属（mention 市场集中度 ≥60% → `news_item.market` 兜底 → 不归属）
    - `aggregate_news_sentiment(session)`：滚动 24h 窗口（`market_overview_news_lookback_hours`，已定案），单条分数取 `news_item.sentiment_score`，缺则 `news_analysis_result.sentiment` 标签映射（positive→+1/neutral→0/negative→-1）；样本 <3 返回 `status="insufficient_data"`；top_signals 取该市场窗口内 `news_signal_result` join `news_item` 按 `signal_confidence` 降序前 5（news_id/title/summary/signal_confidence/source_name/published_at/canonical_url）
- 先写的失败测试：`backend/tests/test_market_sentiment_service.py`（新闻部分）
  - mention 集中/分散/无 mention 三种归属路径；hk→cn 合并；不归属新闻不进任何市场；sentiment_score 缺失回退标签映射；样本不足；top_signals 排序与截断。
- 验收命令：`conda run -n news-caught pytest backend/tests/test_market_sentiment_service.py`
- 依赖：B2。可与 B3/B4 并行。

### B6 — API：`/api/market/overview` 聚合端点 + 配置 CRUD

- 改动文件：
  - `backend/app/schemas/market.py`：新增 `MarketOverviewView / MarketOverviewMarketView / OverviewIndexQuoteView / QuantSentimentView / BoardSectionView / NewsSentimentView / NewsSignalItemView / MarketIndexConfigView / MarketIndexConfigCreateRequest / MarketIndexConfigUpdateRequest`
  - `backend/app/api/routes/market.py`：
    - `GET /overview`：五市场固定骨架（us/cn/kr/jp/eu），组装指数快照 + `compute_market_sentiment` + 板块区（cn=eastmoney / us,eu=preset_etf 从配置表 kind=etf 行取 / kr,jp=none）+ 新闻情绪；读路径不阻塞外网（板块缓存空的零延迟保底抓取带 5s 超时除外）
    - `GET/POST /index-config`、`PATCH/DELETE /index-config/{id}`：POST 校验 market ∈ 五市场、symbol 去空白大写、冲突 409；PATCH 不接受 symbol/market 字段（请求模型不含这两个字段）；DELETE 物理删除
- 先写的失败测试：`backend/tests/test_market_overview_api.py`
  - overview 聚合结构（五市场 key 齐全、空配置市场骨架、板块 source 按市场分流、新闻情绪 insufficient_data 分支）；CRUD（创建成功、重复 409、非法 market 400、PATCH 更新 sort_order/enabled、DELETE 后 404）；鉴权沿用（无 token 401，走现有 conftest 模式）。
- 验收命令：`conda run -n news-caught pytest backend/tests/test_market_overview_api.py`
- 依赖：B1、B3、B4、B5。

### B7 — MarketOverviewProducer worker 与 main.py 接线

- 改动文件：
  - 新增 `backend/app/services/market_overview_producer.py`：BaseWorker 子类，`worker_name="market_overview_producer"`；`do_cycle()` = `refresh_index_quotes` + 东财板块缓存刷新（失败仅记日志）；`get_interval()` = 盘中 60s / 全相关市场闭市 300s（用 `any_overview_market_open`）；不发 event_bus 事件
  - 新增 `backend/app/workers/market_overview_producer.py`：独立进程入口（对齐既有 `workers/market_quote_producer.py`）
  - `backend/app/main.py`：新增 `build_market_overview_producer()`；lifespan 启动段 `if settings.market_overview_producer_enabled: ...start()`；关停段对应 `stop()`
- 先写的失败测试：`backend/tests/test_market_overview_producer.py`
  - mock service/provider：do_cycle 落库且板块失败不影响指数落库；`get_interval` 盘中/闭市取值；异常周期不崩溃（BaseWorker 记账）；main.py 接线（开关关闭时不启动，对齐既有 producer 测试模式）。
- 验收命令：
  - `conda run -n news-caught pytest backend/tests/test_market_overview_producer.py`
  - 后端线收尾回归：`conda run -n news-caught pytest backend/tests`（全量，重点确认既有 `test_market_*`/`test_quote_*` 全绿）
- 依赖：B2、B3（建议 B6 完成后统一验收）。

## 前端线任务（与后端线并行，以设计文档契约为准 + mock 开发）

### F1 — apiClient 方法与类型、mock

- 改动文件：
  - `frontend/src/api/client.ts`：`getMarketOverview / getMarketIndexConfig / createMarketIndexConfig / updateMarketIndexConfig / deleteMarketIndexConfig`（风格对齐现有方法，overview 配 `withMockFallback`）
  - `frontend/src/types/api.ts`：按设计文档九节契约手写 TS 类型（联调 C1 时切换为 generated 类型引用或保持手写并对齐）
  - `frontend/src/api/mock.ts` 及 `frontend/src/api/mock/`：overview 五市场 mock 数据（含 us 完整、kr/jp boards=none、新闻情绪 insufficient_data 样例）
- 先写的失败测试：`frontend/src/api/client.test.ts` 增补（新方法 URL/方法/载荷断言，mock 降级路径）。
- 验收命令：`npm --prefix frontend test -- --run client`

### F2 — marketOverviewStore

- 改动文件：新增 `frontend/src/stores/marketOverviewStore.ts`（overview/loading/error/lastLoadedAt、`loadOverview()`、60s 定时器 start/stop、配置 CRUD action 保存后自动 `loadOverview()`）
- 先写的失败测试：`frontend/src/stores/marketOverviewStore.test.ts`（加载成功/失败态、CRUD 后触发刷新、定时器启停）。
- 验收命令：`npm --prefix frontend test -- --run marketOverviewStore`
- 依赖：F1。

### F3 — MarketOverviewCard 组件

- 改动文件：新增 `frontend/src/components/watchlist/MarketOverviewCard.vue`（市场名+开闭市徽标、指数行列表、量化情绪 chip 五色映射、新闻情绪分数+信号列表点击 `router.push('/news/{id}')`、板块区按 source 渲染：eastmoney 榜 / preset_etf 列表 / none 不渲染；kr/jp/eu 新闻情绪"暂无数据"优雅降级；涨跌配色沿用现有 StockCard 约定）
- 先写的失败测试：`frontend/src/components/watchlist/MarketOverviewCard.test.ts`（chip 映射含 unknown/insufficient_data、板块区三种 source 渲染分支、信号点击跳转、红涨绿跌/绿涨红跌市场约定）。
- 验收命令：`npm --prefix frontend test -- --run MarketOverviewCard`
- 依赖：F2。

### F4 — MarketOverviewPanel + WatchlistView 集成

- 改动文件：
  - 新增 `frontend/src/components/watchlist/MarketOverviewPanel.vue`（五张卡片容器 + 右上"配置"按钮）
  - `frontend/src/views/WatchlistView.vue`：Tab 切换之上挂 `<MarketOverviewPanel />`，`onMounted` 加载并启动定时器、`onUnmounted` 清理
- 先写的失败测试：`frontend/src/views/WatchlistView.test.ts` 增补（面板挂载、卸载清理定时器、加载失败不破坏既有 Tab 区）。
- 验收命令：`npm --prefix frontend test -- --run WatchlistView`
- 依赖：F3。

### F5 — MarketIndexConfigModal 配置弹窗

- 改动文件：新增 `frontend/src/components/watchlist/MarketIndexConfigModal.vue`（按市场分组表格：启用开关/排序/名称编辑/删除 + 底部新增表单：市场下拉/symbol/名称/kind；校验失败就地提示，对齐 `WatchlistAddModal.vue` 交互模式）
- 先写的失败测试：`frontend/src/components/watchlist/MarketIndexConfigModal.test.ts`（新增校验拦截、保存调用 store action、删除确认、保存后列表刷新）。
- 验收命令：`npm --prefix frontend test -- --run MarketIndexConfigModal`
- 依赖：F2（建议 F4 完成后做，集成进 Panel 的"配置"按钮）。

## 联调与收尾

### C1 — 契约同步与全量验证

- 改动文件：
  - `frontend/openapi.json`、`frontend/src/types/generated/api.d.ts`（自动生成）
  - 如 generated 类型与 F1 手写类型有出入，以 generated 为准修正 `frontend/src/types/api.ts` 与相关组件
  - `docs/code-change-log.md` 逐任务记录补齐
- 步骤（按序）：
  1. `conda run -n news-caught python scripts/export_openapi.py`
  2. `npm --prefix frontend run generate:api`
  3. 后端全量：`conda run -n news-caught pytest backend/tests`
  4. 前端全量单测：`npm --prefix frontend test -- --run`
  5. 前端构建：`npm --prefix frontend run build`
  6. 手动冒烟：`./scripts/dev.sh` 起本地服务 → Watchlist 页顶部出现五市场卡片、指数有报价（或明确的延迟/失败态）、配置弹窗增删改生效、信号点击跳转新闻详情、东财板块榜在 cn 卡片展示（断网/接口失败时显示 stale/不可用而非报错）
- 依赖：B6、B7、F5 全部完成。

## 风险执行要点

- 东财接口实测字段若与设计（f12/f14/f3/f104/f105/f106/f62）不符，以实测为准调整解析并在 change log 记录；解析必须保持防御性，字段缺失不抛错。
- 实施中若发现 yfinance 对 `^STOXX50E`/`^KS11` 批量下载缺数据，允许在该 ticker 级别降级为逐票 `fetch_quote`（provider 已有此回退），并在 change log 记录实测结果。
- 每完成一个任务立即更新 change log；不要积攒到 C1 一次性补写（任务级记录，C1 只做收尾记录）。
