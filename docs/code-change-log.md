# 代码变更记录

> 用于记录本项目每一次实际修改。新增记录时，追加到最上方。
>
> **阅读范围：** 开始较大改动前，只读本文件顶部近期条目，确认是否与正在改的模块冲突。
> 不要把本文件或历史归档当作待办清单。2026-07 及更早的记录见 [archive/code-change-log-before-2026-08.md](./archive/code-change-log-before-2026-08.md)。

## 2026-08-18 量化交易台补全：真实选票流水线、个股 K 线、首页仪表盘与默认策略

- 修改人：Claude（三个 Sonnet 子智能体并行实施 + 协调者收尾）
- 修改范围：选票内核从合成夹具升级为真实行情驱动；个股研究页 K 线/资金流；交易台首页图形化仪表盘；策略工作台因子表与默认策略种子；K 线接口解除自选股绑定；东财回填健壮性。设计与计划见 `docs/archive/superpowers/` 下 2026-08-18 real-pipeline 两篇。
- 变更内容：
  - 新增 `run_market_pipeline`（`scenario=real`，`QuantRunRequest.scenario` 默认改 real）：data_gate（无行情 → DEGRADED+no_market_data）→ 真实 U2（bar 数≥120、20 日中位成交额≥1e8、最新交易日有 bar）→ 三 sleeve 打分首次接入 `factors.py`（trend 用最新主力净流入+20 日均成交额，可 qualify；event 用近 7 日 rule mention 聚合，grade C 只进 WATCH；fundamental 显式 no_financials gap 不产候选）→ 涨跌停开盘不可成交降级 → 状态机/排名/result_hash 复用。`get_proposal` 的 allocate vol 改用 20 日日收益标准差。实测（29 只真实库）：14 候选、000034.SZ 神州数码 trend qualified、提案 8% 仓位 + 92% 现金。
  - 新增 `GET /api/quant/factors`；`scripts/seed_demo_data.py` 幂等种子 3 条探索性默认策略（每 sleeve 一条）。
  - `DeskStockView` 加 K 线卡（日/周，复用 KlineChart + `getStockKline`）与 A 股 FundFlowPanel；`MarketChartService.get_kline` 自选股未命中时按代码后缀推断市场（`_resolve_kline_symbol`），交易台候选不再 404。
  - `DeskView` 状态带下新增「交易台仪表盘」（覆盖率进度条、三 sleeve 漏斗、最近运行徽章、提案权重条，纯 CSS）；「手动重跑」默认发 `real`。`DeskStrategiesView` 加因子注册表表格与「填入示例」。
  - 回填：`backfill.py` 每 symbol 失败重试 3 次（2s/8s/30s 退避）；`backfill_main.py` 支持 `QUANT_BACKFILL_LIMIT/SLEEP/DAYS`。实测东财对连续抓取限流（代理与直连均断），断点续传 + 退避循环可恢复。
- 影响文件：`backend/app/services/quant/recommendation/market_pipeline.py`（新）、`backend/app/services/quant/contracts.py`、`backend/app/services/quant_desk_service.py`、`backend/app/api/routes/quant.py`、`backend/app/schemas/quant.py`、`backend/app/services/market_chart_service.py`、`backend/app/services/quant/market_data/backfill{,_main}.py`、`scripts/seed_demo_data.py`、`backend/tests/quant/test_market_pipeline.py`（新）、`backend/tests/test_kline_non_watchlist.py`（新）、`backend/tests/quant/test_market_backfill.py`、`backend/tests/test_quant_api.py`、`frontend/src/views/Desk{View,StockView,StrategiesView}.{vue,test.ts}`、`frontend/src/stores/deskStore.ts`、`frontend/src/api/client.ts`、`frontend/src/api/mock/quant.ts`、`frontend/src/types/{api.ts,generated/api.d.ts}`、`frontend/openapi.json`、`docs/current-state.md`。
- 接口/数据结构变化：新增 `GET /api/quant/factors`；`POST /api/quant/recommendations/run` 的 `scenario` 增加 `real` 并作为默认值（旧值 abstain/mixed 兼容）；`GET /api/market/symbols/{symbol}/kline` 对可推断市场的非自选股标的从 404 变为正常返回（无法推断仍 404）。无表结构变化。
- 验证情况：后端 `pytest backend/tests/quant backend/tests/test_quant_api.py` 63 passed，kline/market 相关 47 passed，回填 3 passed；全量 1302 passed / 7 failed——该 7 个 news 失败为**基线预先存在的测试顺序污染**（干净 HEAD worktree 全量跑有 13 个失败，含这 7 个；均单测隔离可过），非本次引入。前端全量 vitest 546 passed、`vue-tsc -p tsconfig.app.json` 零错、`npm run build` 通过、`check:api-drift` OK。活服务实测：POST run(real) 出真实候选、提案/因子/策略/K 线端点全部验证通过。
- 风险或后续事项：东财/腾讯源无 SLA；行情仍无每日自动增量 worker（手动 `make quant-backfill`）；BSE 板块推断对 `9xxxxx.BJ` 归为 MAIN（当前池内无 BJ 标的，未触发）；event sleeve 仅对过 U2 流动性门槛的标的打分；K 线 Redis 缓存可能缓存到"抓取瞬时失败的空 candles"（TTL 300s 自愈）；基线全量套件的测试顺序污染问题待专项修复。

## 2026-08-18 量化交易台 Phase 2～5：研究包、三 sleeve、DSL 回测与模拟盘

- 修改人：Cursor Grok
- 修改范围：量化交易台产品面与内核收口（Phase 2 个股研究/雷达/AI 审计，Phase 3 打分/提案/成绩单，Phase 4 DSL/回测实验室，Phase 5 模拟盘/决策日志/副驾只读工具）；未改现有 `GET /api/backtest`。
- 变更内容：主库新增研究包/雷达/AI 审计、组合提案、策略、回测、模拟盘与决策日志表。新闻 mention 进入快循环雷达，D 级不得 qualified。研究包缺财务时显式 gap，不编造价格锚；「问 AI」经 `desk_symbol` 装载只读上下文。三 sleeve 规则打分 + 分配器（单票 ≤8%、现金 ≥10%），LLM 不改排名/仓位。DSL 只允许因子注册表，walk-forward 标记 exploratory 且 `qualified=false`。模拟盘需确认后撮合，停牌拒单。前端补齐 `/desk/stocks/:symbol`、`/desk/portfolio-proposal`、`/desk/report-card`、`/desk/strategies`、`/desk/backtest`，运行中心 Runs/AI 审计/决策日志 Tab，`/portfolio` 增加模拟盘条。
- 影响文件：`backend/app/services/quant/`、`backend/app/services/quant_desk_service.py`、`backend/app/api/routes/quant.py`、`backend/app/models/quant.py`、`backend/alembic/versions/a8c4e1f6b902_*`、`backend/alembic/versions/b9d5f2a7c013_*`、`backend/tests/quant/`、`backend/tests/test_quant_api.py`、`frontend/src/views/Desk*.vue`、`frontend/src/views/PortfolioView.vue`、`frontend/src/router/index.ts`、`frontend/src/components/layout/AppShell.vue`、`frontend/openapi.json`、`docs/current-state.md`；计划与设计已归档到 `docs/archive/superpowers/`。
- 接口/数据结构变化：新增 `/api/quant/symbols/{symbol}/research|events`、`/api/quant/ai/*`、`/api/quant/recommendations/runs`、`/api/quant/portfolio-proposals/latest`、`/api/quant/report-card`、`/api/quant/strategies*`、`/api/quant/backtests`、`/api/quant/paper/*`、`/api/quant/decision-log`、`/api/quant/copilot/tools`；`/api/llm/chat` 增加可选 `desk_symbol`。无旧接口破坏。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news_caught_quant_p25b.db conda run -n news-caught pytest backend/tests/quant backend/tests/test_quant_api.py backend/tests/test_news_signal_pipeline.py backend/tests/test_migration_parity.py` 为 58 passed；`ruff check` 覆盖量化后端文件通过；前端 Desk/Ops/Proposal/ReportCard/Strategies/Backtest/Portfolio/router/AppShell/smoke/chat 共 85 passed；`npm --prefix frontend run build` 与 `check:api-drift` 通过。
- 风险或后续事项：流水线仍可用合成夹具；真实东财回填与财务/一致预期未采购，成绩单只展示漏斗不计超额收益；探索性回测不得晋级。单测禁止打东财真网。

## 2026-08-18 量化交易台 Phase 1：独立行情库、mention 主链路、运行中心与资金流

- 修改人：Cursor Grok
- 修改范围：独立 `market_data.db`、东财日线/资金流解析与回填、新闻 rule mention、`/api/quant` 覆盖率与资金流、`/desk/ops` 与个股资金流面板；未改现有 `/api/backtest` 与 `/portfolio`。
- 变更内容：新增与主库隔离的行情库 Alembic（`alembic_version_market`）及 `daily_bar` / `index_daily_bar` / `trade_calendar` / `fund_flow_daily`。东财历史 K 线与个股资金流解析走 fixture 测试，不在单测里打真实网；`make quant-backfill` 分批回填前 100 只 A 股、支持断点续传。新闻 pipeline 阶段 2 写入 `mention_type=rule` 的 A 股映射（名称≥3 字、短名停用词、6 位代码）。`GET /api/quant/data/status` 读取真实覆盖率；新增 `GET /api/quant/symbols/{symbol}/fund-flow`。前端交易台增加「运行中心」`/desk/ops`（数据健康 Tab），个股详情对 A 股展示资金流空态/表格；`/desk` 不再把 `/desk/ops` 当成机会雷达高亮。
- 影响文件：`backend/app/db/market_*.py`、`backend/app/models/market_data.py`、`backend/alembic_market/`、`alembic_market.ini`、`backend/app/services/quant/market_data/`、`backend/app/services/quant/mention_backfill.py`、`backend/app/services/news_signal_pipeline.py`、`backend/app/services/quant_desk_service.py`、`backend/app/api/routes/quant.py`、`backend/app/schemas/quant.py`、`backend/tests/quant/`、`backend/tests/test_quant_api.py`、`backend/tests/test_news_signal_pipeline.py`、`Makefile`、`frontend/src/views/DeskOpsView.vue`、`frontend/src/components/watchlist/FundFlowPanel.vue`、`frontend/src/views/WatchlistDetailView.vue`、`frontend/src/router/index.ts`、`frontend/src/components/layout/AppShell.vue`、`frontend/openapi.json`、`docs/current-state.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：新增 `GET /api/quant/symbols/{symbol}/fund-flow`；`GET /api/quant/data/status` 增加 `daily_bar_count` / `symbol_count` / `fund_flow_count` / `last_trade_date`。行情表只写 `market_data.db`，不进 `app.db`。无旧接口破坏。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news_caught_quant_p1.db conda run -n news-caught pytest backend/tests/quant backend/tests/test_quant_api.py backend/tests/test_news_signal_pipeline.py backend/tests/test_migration_parity.py` 为 39 passed；另补 `test_quant_api.py` 覆盖率用例后该文件 7 passed；`ruff check` 覆盖新增后端文件通过；前端 Desk/DeskOps/FundFlow/WatchlistDetail/router/AppShell/smoke 共 61 passed；`npm --prefix frontend run build` 与 `check:api-drift` 通过。
- 风险或后续事项：未执行真实东财回填（单测禁止打网）；覆盖率相对全量约 6141 只 A 股，默认 CLI 只回填前 100 只。公司行动/龙虎榜/两融、真实三 sleeve 打分与雷达 worker 仍属后续 Phase。Phase 0/1 计划已归档到 `docs/archive/superpowers/plans/`。

## 2026-08-18 量化交易台 Phase 0：决策契约、合成流水线与 /desk 骨架首页

- 修改人：Cursor Grok
- 修改范围：量化域后端内核、主库三张业务表、`/api/quant` 骨架、默认首页与交易台导航；未改现有新闻主链路、`/api/backtest` 与 `/portfolio`。
- 变更内容：落地 point-in-time 截点、财务修订、除权 total-return、分板块涨跌停/T+1/停牌拒单、U0/U2 历史股票池与候选状态机；用合成夹具贯通事件/趋势/基本面三 sleeve，资格未过线时返回 0 条 qualified（现金合法）且同版本 run hash 可复现。主库新增 `recommendation_run` / `recommendation_item` / `quant_run_stage_log`。新增 `GET/POST /api/quant/recommendations/*`、`GET /api/quant/data/status`、`GET /api/quant/radar`。前端默认首页改为 `/desk`（状态带 + 空态机会流 + 手动重跑），导航置顶「交易台」，原「信号回测」文案改为「信号统计」。`requirements.txt` 显式锁定 `pandas==3.0.1`、`numpy==2.4.3`，新增 `pyarrow==21.0.0`。
- 影响文件：`backend/app/services/quant/`、`backend/app/services/quant_desk_service.py`、`backend/app/models/quant.py`、`backend/app/api/routes/quant.py`、`backend/alembic/versions/f7a1b8c2d4e0_add_quant_recommendation_tables.py`、`backend/tests/quant/`、`backend/tests/test_quant_api.py`、`frontend/src/views/DeskView.vue`、`frontend/src/stores/deskStore.ts`、`frontend/src/router/index.ts`、`frontend/src/components/layout/AppShell.vue`、`frontend/openapi.json`、`requirements.txt`、`docs/superpowers/plans/2026-08-18-quant-desk-phase0-plan.md`、`docs/current-state.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：新增 `/api/quant/*` 四个端点与三张主库表；无旧接口破坏。LLM 不参与排名。独立 `market_data.db` 仍未创建。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news_caught_quant_phase0.db conda run -n news-caught pytest backend/tests/quant backend/tests/test_quant_api.py backend/tests/test_migration_parity.py` 为 25 passed；`ruff check` 覆盖新增后端文件通过；前端 Desk/router/AppShell/smoke 共 49 passed；`npm --prefix frontend run build` 与 `check:api-drift` 通过。
- 风险或后续事项：Phase 0 流水线仅合成数据，页面空态是预期产品行为而非故障。`pyarrow` 已写入依赖但本期未使用。下一步见 Phase 1 计划。

## 2026-08-18 量化交易台 v2：盈利目标、个股情报与组合风控深化

- 修改人：Codex
- 修改范围：深化现有量化交易台设计；未改运行时代码。
- 变更内容：从净超额收益、可成交性和回撤约束倒推系统目标，把原单一综合分拆为事件/催化、趋势/资金、基本面重估三个独立 sleeve；新增快慢双循环、候选状态机、可输出 0～N 个机会和现金结果，取消 LLM 直接 TopN 排名，限定其只做证据抽取、纵横分析与反方审查。补充 point-in-time 数据契约、历史证券池/规则版本、官方公告与财务事实、SQLite + Parquet 特征存储、因子准入实验、个股纵横研究包、产业链雷达、组合风险预算/退出规则、严格 walk-forward 回测与策略晋级门槛，并把实施顺序重排为 Phase 0～5。
- 影响文件：`docs/superpowers/specs/2026-08-18-quant-trading-desk-design.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：无运行时变化；设计草案新增/调整 `security_master_history`、`trading_rule_version`、`financial_fact`、`corporate_event`、`research_snapshot`、`portfolio_proposal`、`decision_log` 等数据结构，并扩充 `/api/quant/radar`、个股研究、组合提案、因子研究和模拟订单端点。
- 验证情况：纯文档修改，未运行前后端测试；已阅读 `README.md`、`docs/current-state.md`、近期变更记录及现有 `stock_research_synthesis`、`watchlist_research_service`、新闻信号管线与依赖配置；已联网核验 2026 年沪深北交易规则、沪深港通披露调整、印花税/交易费用、巨潮公告入口和回测过拟合方法依据；完成章节/内部引用与 diff 检查。
- 风险或后续事项：系统只能提高研究与风险控制质量，不能保证盈利；账户规模、最大回撤、数据源授权/采购、历史退市股覆盖和产业链关系维护仍需用户在开工前确定优先级。设计终审后再为 Phase 0 编写独立 TDD 实施计划。

## 2026-08-18 量化交易台设计方案 v3：AI 接入层与前端/可观测性补全

- 修改人：Claude
- 修改范围：设计文档更新（v2→v3）；未改运行时代码。
- 变更内容：在 Codex v2 深化版（第一性原理、三 sleeve、point-in-time 契约、候选状态机、组合风控、晋级治理）之上完成 v3 补全：（1）新增 §8「AI 接入层」——四角色×模型三档路由（新表 `llm_role_binding`）、研究副驾（复用 ChatView/`/api/llm/chat` 基座，新增 `toolset=desk_readonly` 只读工具调用循环）、prompt 治理与注入防护、成本分池与固定降级顺序、调用审计（新表 `ai_call_audit`）与抽取/Skeptic 质量评测；（2）重写 §13「前端设计」——机会雷达首页仪表盘五分区详设、机会卡收起/展开态、个股研究页、组合提案页、回测报告页布局、成绩单漏斗/归因/校准视图，以及新增 `/desk/ops` 运行中心（run 阶段时间线、数据健康、AI 审计、决策日志四 Tab，新表 `quant_run_stage_log`）；（3）分期计划每期补「产品可见增量」并把 AI/前端交付并入 Phase 0-5；（4）全文章节重排（原 §8-17 顺延为 §9-18），修正交叉引用；风险表新增提示注入与 AI 成本两行，开放问题新增 MCP 化与存量 prompt 治理两项。
- 影响文件：`docs/superpowers/specs/2026-08-18-quant-trading-desk-design.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：无（`quant_run_stage_log`、`ai_call_audit`、`llm_role_binding` 三表与 `/quant/runs/{id}`、`/quant/ai/*`、`/quant/copilot/tools`、`/llm/chat` 扩展参数等端点均为设计草案，尚未实现）。
- 验证情况：纯文档修订，未运行测试；v2 内容经逐节核对全部保留，仅编号顺延与少量衔接句调整（§6.3、§7 指向 §8 的路由说明）。
- 风险或后续事项：AI 副驾会话保留 localStorage 形态（单机单用户权衡，文档已注明）；v2 §2.1 边界修正与 v3 补充均待用户终审后回填为正式边界；存量 9 处散落 prompt 的治理未纳入本方案主线，列为开放问题 7。

## 2026-08-18 量化交易台重构设计方案

- 修改人：Claude
- 修改范围：新增设计文档；未改运行时代码。
- 变更内容：经两轮边界讨论确认后（A 股为主、因子打分初筛+LLM 精选、自研轻量向量化回测、条件组合器 DSL、盘后自动+手动重跑、全量 A 股 2～3 年日线独立库、交易台设为新首页、纳入成绩单/模拟盘/龙虎榜两融），产出量化交易台整体重构设计：独立行情库 `market_data.db` 与采集器、`news_stock_mention` 主链路补齐、因子注册表与合成打分、每日推荐流水线（LLM 失败降级为规则版）、策略 DSL 与向量化回测引擎（T+1/涨跌停/费用模型）、推荐成绩单前向收益追踪、模拟盘 paper_* 体系、前端 `/desk` 系列页面与 API 草案，并给出四期实施计划与验收标准。
- 影响文件：`docs/superpowers/specs/2026-08-18-quant-trading-desk-design.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：无（文档中的新表与 `/api/quant/*` 端点为设计草案，尚未实现）。
- 验证情况：纯文档新增，未运行测试；文档中现状描述基于 2026-08-18 对代码库的实际探查（含 mention 写入点、资金流仅板块级、signal_backtest 为命中率统计等结论）。
- 风险或后续事项：北向个股数据受披露政策限制已降级为大盘级因子；回测存在幸存者偏差（退市股不在池）；pandas/numpy 需在实现期提升为显式锁定依赖；开放问题现见 v2 设计文档 §16，待用户终审后按分期出 plan 文档。

## 2026-08-18 归档过期文档，隔离历史方案对后续开发的影响

- 修改人：Cursor Grok
- 修改范围：文档导航、现行/归档边界、智能体协作入口；未改运行时代码。
- 变更内容：将 `docs/superpowers/` 中 2026-06 至 2026-08 已完成的设计与计划全部迁入 `docs/archive/superpowers/`，现行目录只保留进行中工作的占位说明。把 2026-07 及更早的变更流水拆到 `docs/archive/code-change-log-before-2026-08.md`。将启动期 `plan.md`、项目管理计划、并行开发提示词和 Master Lin 优化诊断清单迁入 `docs/archive/bootstrap/`，根目录 `plan.md` 改为指向现状入口。新增 `docs/current-state.md` 作为 2026-08-18 系统快照；更新 `AGENTS.md`、`docs/README.md`、`README.md` 和若干第一阶段草稿的状态说明，明确归档内容与旧“未做/后续事项”不自动继承为新任务。
- 影响文件：`AGENTS.md`、`README.md`、`plan.md`、`docs/README.md`、`docs/current-state.md`、`docs/code-change-log.md`、`docs/product-requirements.md`、`docs/technical-architecture.md`、`docs/api-contract.md`、`docs/stability-and-evolution.md`、`docs/superpowers/`、`docs/archive/`。
- 接口/数据结构变化：无。
- 验证情况：已核对归档前后 `docs/superpowers` 仅剩 `.gitkeep` 与 README；现行变更记录约 310 行，历史变更约 5233 行迁入归档；未运行前后端测试（纯文档整理，无运行时行为变化）。
- 风险或后续事项：`docs/product-requirements.md`、`docs/technical-architecture.md`、`docs/api-contract.md` 仍可能落后于代码，本次只加了状态说明，未重写成 as-built 架构文档。changelog 与设计稿中的旧路径字符串未逐条改写。

## 2026-08-03 LLM 配置弹窗与 Token 用量可视化优化

- 修改人：Codex
- 修改范围：LLM 设置页配置入口、配置弹窗、模型配置表单、Token 用量账本与趋势图、前端测试；已合并工作树和本地功能分支清理。
- 变更内容：将原本常驻页面的大模型配置表单收起为紧凑的“MODEL ACCESS”提示入口，点击新增或模型列表中的编辑按钮后复用居中弹窗；弹窗限制为 `88vh` 并在内部滚动，支持遮罩、关闭按钮、取消按钮和 Escape 关闭，保存成功后自动关闭并刷新用量统计，保存失败时保留窗口；配置字段改为双列/三列紧凑布局，保留服务预设、API Key 不回显和 Base URL 变化时重新校验 Key 的既有语义。Token 用量区重做为紧凑指标带、输入/输出占比、预算进度、按日堆叠柱状图、模型实际 Token 排行和操作类型标签，单日数据也能形成可读图形。清理前逐一确认五个功能工作树干净且对应提交已进入 `main`，随后移除工作树目录及本地 `feature/frontend-optimization`、`feature/llm-optimization`、`feature/logging-optimization`、`feature/watchlist-optimization`、`feature/dashboard-optimization` 分支，仅保留主工作树和无关/保护分支。
- 影响文件：`frontend/src/views/LlmSettingsView.vue`、`frontend/src/views/LlmSettingsView.test.ts`、`frontend/src/components/llm/LlmConfigModal.vue`、`frontend/src/components/llm/LlmConfigForm.vue`、`frontend/src/components/llm/LlmConfigList.vue`、`frontend/src/components/llm/TokenUsageConsole.vue`、`frontend/src/components/llm/TokenUsageConsole.test.ts`、`frontend/src/components/llm/TokenTrendChart.vue`、`frontend/src/components/llm/TokenTrendChart.test.ts`、`docs/superpowers/specs/2026-08-03-llm-settings-modal-usage-redesign-design.md`、`docs/superpowers/plans/2026-08-03-llm-settings-modal-usage-redesign-plan.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：无；继续使用现有 LLM 配置接口与 `/api/llm/stats` 响应结构，未修改数据库。
- 验证情况：TDD 新增预期在旧布局下失败，完成后 LLM 设置、Token 用量账本与趋势图专项共 14 tests passed；前端全量 `npm --prefix frontend test -- --run --maxWorkers=1` 为 87 files / 511 tests passed；`npm --prefix frontend run build` 通过；`git diff --check` 通过。浏览器在 1452×743 视口实测默认页保持紧凑，新增和编辑均打开同一居中弹窗，编辑态字段正确带入，弹窗约 896×654、内部可滚动，单日 Token 堆叠柱可读，控制台无错误。
- 风险或后续事项：弹窗当前提供常用关闭方式但未实现完整焦点循环；统计图按接口当前最多七日数据设计，若未来扩展为更长时间范围，需增加横向滚动或时间粒度切换。根目录既有未跟踪 `node_modules/` 未纳入本次修改或提交。

## 2026-08-03 LLM 设置弹窗化与用量账本重设计方案

- 修改人：Codex
- 修改范围：LLM 设置页面配置交互和 Token 用量可视化设计、TDD 实施计划。
- 变更内容：基于用户截图确定移除常驻大表单，页面改为紧凑配置提示与按需居中弹窗；新增/编辑复用同一窗口，保存成功关闭；用量区从四张等权卡、稀疏折线和传统表格改为紧凑指标带、输入/输出堆叠柱、模型占比排行和预算轨道；补充测试边界、无障碍关闭方式和分步实现计划。
- 影响文件：`docs/superpowers/specs/2026-08-03-llm-settings-modal-usage-redesign-design.md`、`docs/superpowers/plans/2026-08-03-llm-settings-modal-usage-redesign-plan.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：无；继续使用现有 LLM 配置接口和 `/api/llm/stats` 数据结构。
- 验证情况：设计阶段已检查 `LlmSettingsView`、`LlmConfigForm`、`LlmConfigList`、`TokenUsageConsole`、`TokenTrendChart` 及现有测试；纯文档阶段未运行测试或构建。
- 风险或后续事项：模态表单字段较多，需限制窗口高度并让内容内部滚动；实现阶段必须确认编辑配置注入和保存后关闭不会破坏 API Key 保留语义。

## 2026-08-03 五工作树终审与主分支集成

- 修改人：Codex
- 修改范围：前端、LLM、日志、Dashboard 四个非空优化分支的代码评审、缺陷修复、独立提交、冲突合并和集成验证；自选股空分支审计。
- 变更内容：审计确认五个工作树均从 `0ca4827` 创建，其中自选股分支无提交且工作区干净，按无变更处理；对其余四个分支补充 TDD 审查，修复访问日志上下文/敏感查询、前端卸载上报鉴权、聊天窄屏不可访问、行情闪烁计时器泄漏和 `.env.example` 未跟踪问题；分别提交后按日志 → LLM → Latest Events → Dashboard 顺序以独立 merge commit 合入 `main`；冲突中保留所有变更记录，并让 `llm_providers.py` 同时包含日志增强与 reasoning 流、`useChatSessions.ts` 同时包含前端 logger 与 reasoning 消息字段；AppShell 同时保留顶部状态条移除和桌面聊天视口锁定，因状态条已删除将聊天主区改为单一 `minmax(0,1fr)` 行，避免空 auto 行压缩内容。
- 影响文件：四个功能分支的全部文件；集成冲突与补充文档重点涉及 `frontend/src/components/layout/AppShell.vue`、`frontend/src/components/layout/AppShell.test.ts`、`backend/app/services/llm_providers.py`、`frontend/src/composables/useChatSessions.ts`、`frontend/openapi.json`、`frontend/src/types/generated/api.d.ts`、`docs/superpowers/specs/2026-08-03-worktree-integration-design.md`、`docs/superpowers/plans/2026-08-03-worktree-integration-plan.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：新增 `POST /api/logs/frontend`；所有 HTTP 响应新增 `X-Request-ID`；`POST /api/llm/chat` SSE 新增可选 `reasoning` 帧。无数据库结构变化；其余均为前端展示或日志行为增强。
- 验证情况：各分支专项测试和构建通过；主分支后端全量 `NEWS_CAUGHT_TEST_DB=/tmp/news_caught_main_integration.db conda run -n news-caught pytest backend/tests -q` 为 1237 passed / 8 failed，其中 7 个为既有 `test_news.py` / `test_news_analysis.py` 顺序污染，用独立全新测试库复跑两文件 28 passed，另 1 个 `test_search_a_shares_performance` 在单独复跑时仍为 0.486s > 0.3s，属既有机器相关性能阈值问题；前端全量 `npm --prefix frontend test -- --run --maxWorkers=1` 为 86 files / 508 tests 全绿；`npm --prefix frontend run build` 通过；`conda run -n news-caught ruff check backend/app backend/tests backend/scripts` 通过；OpenAPI export check 与 `check:api-drift` 通过；重新生成并提交 `frontend/openapi.json` 与 `frontend/src/types/generated/api.d.ts`；`alembic heads` 为单一 `e6c2a9f4d1b7`；`git diff --check` 通过。
- 风险或后续事项：后端仍有已记录的新闻测试顺序污染和 A 股搜索性能阈值抖动；LLM 预设模型名可能随供应商更新；多进程写同一轮转日志文件仍需未来专项治理。合并前保护分支为 `backup/main-before-worktree-integration-20260803`。

## 2026-08-03 日志分支合并审查与安全加固

- 修改人：Codex
- 修改范围：请求访问日志上下文与敏感信息保护、前端卸载日志上报鉴权、独立抓取入口日志配置、环境变量示例和配套设计/计划。
- 变更内容：修复正常 HTTP 请求在清理 contextvar 后才记录访问日志、导致 `app.access` 缺失 `request_id` 的生命周期问题；访问日志创建 `LogRecord` 时显式写入 `request_id/task_id/log_ctx`，不再依赖 handler filter 的执行顺序，兼容测试或运行时重配 root logger；访问日志对 `token`、`app_token`、`access_token`、`api_key`、`authorization` 查询值统一脱敏，并避免重复追加 `X-Request-ID` 响应头；前端 `pagehide` 上报由无法携带 `X-App-Token` 的 `sendBeacon` 改为带鉴权请求头的 keepalive fetch；独立 `news_fetcher` 入口补齐日志文件、轮转和格式参数；调整 `.gitignore` 允许根目录 `.env.example` 纳入版本控制；补充日志加固设计与计划文档。
- 影响文件：`backend/app/core/request_logging.py`、`backend/tests/test_request_logging.py`、`backend/app/workers/news_fetcher.py`、`frontend/src/utils/logger.ts`、`frontend/src/utils/logger.test.ts`、`.gitignore`、`.env.example`、`docs/superpowers/specs/2026-08-03-logging-observability-hardening-design.md`、`docs/superpowers/plans/2026-08-03-logging-observability-hardening-plan.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：无新增接口或数据库变化；`POST /api/logs/frontend` 契约不变。访问日志中的敏感查询值由明文改为 `***`，属于安全收紧。
- 验证情况：TDD 红灯确认普通访问日志缺少 `request_id` 且敏感查询值明文出现；首次修复通过专项测试后，全量套件进一步暴露 handler 重配置场景仍会丢字段，已改为 LogRecord 显式上下文并复测。日志专项后端测试 28 passed，前端 logger 测试 10 passed；Ruff 与前端构建通过。二次修复后的分支全量后端结果为 1234 passed / 9 failed：7 个为既有新闻测试顺序污染，1 个为 A 股搜索性能阈值抖动，1 个为工作树绝对路径测试；本次新增及修改的日志测试全部通过。
- 风险或后续事项：keepalive 请求受浏览器卸载传输大小限制，当前客户端队列和批大小限制使常规错误批次处于可接受范围；多进程日志轮转竞态仍沿用原分支记录的后续事项。

## 2026-08-02 日志系统重构：结构化增强 + 链路透传 + alembic 冲突根治 + 前端日志封装与上报

- 修改人：Claude
- 修改范围：后端日志基础设施（core/logging、上下文透传、访问日志中间件、alembic 配置统一）、前端日志上报端点、163 处后端日志调用点逐点梳理、前端 logger 封装与 11 处 console.error 替换。
- 变更内容：
  1. **核心封装增强**（`backend/app/core/logging.py`）：`_JsonFormatter` 补全 `module/lineno` 字段并修复 `logger.exception()` 堆栈在 json 模式下整体丢失的问题（新增 `exc`/`stack` 字段）；plain 格式改为 `_PlainFormatter`，支持追加上下文后缀。新增 `backend/app/core/log_context.py`：contextvars 承载 `request_id`/`task_id`，`LogContextFilter` 以 handler filter 形式注入 LogRecord（json 输出独立字段、plain 输出 ` [req=… task=…]` 后缀，对第三方库日志同样生效）。
  2. **链路透传与访问日志**：新增 `backend/app/core/request_logging.py` 的 `RequestLoggingMiddleware`（纯 ASGI，规避 BaseHTTPMiddleware 对 SSE 的缓冲问题）——生成/透传并回写 `X-Request-ID`（入站值经白名单字符与长度清洗）、以 logger `app.access` 记录 method/path/status/耗时/客户端（5xx 记 warning），按前缀排除（默认 `/api/health,/api/stream`，排除时 request_id 仍透传）。`BaseWorker._run_loop` 每周期绑定 `task_id={worker_name}#{seq}`，多 worker 交织日志可按周期串联。Makefile `backend` 目标加 `--no-access-log` 避免与 uvicorn 自带访问日志重复。
  3. **alembic 双配置冲突根治**：`app/db/initializer.py` 已用 alembic 官方 `configure_logger=False` attribute 阻止 fileConfig 接管日志，据此删除 `pipeline_worker_main.py` 中"迁移后摘 handler 再重配"的过时补救逻辑（含 `_MANAGED_HANDLER_ATTR` 导入），补回归测试钉死前提。
  4. **前端错误日志上报**：新增 `POST /api/logs/frontend`（`backend/app/api/routes/logs.py` + `schemas/frontend_log.py`，挂 api_router 继承鉴权）——批量接收 warn/error 条目落入 logger `frontend`，三层防滥用：单批 ≤20 条（超出 413）、单字段截断（message/stack ≤2000 字符）、进程级滑动窗口限流（默认 120 条/分钟，超额静默丢弃仍返 200）。
  5. **前端 logger 封装**：新增 `frontend/src/utils/logger.ts`（debug/info dev-only，warn/error 恒输出；prod 下 error 批量上报——5s 定时或攒 10 条 flush、30 条/分钟客户端限流、失败静默不重入、pagehide 走 sendBeacon；传输层独立原生 fetch + 复用 `__APP_TOKEN__` → `X-App-Token` 机制，不 import api client 避免循环依赖）。替换全部 11 处裸 `console.error`。
  6. **163 处调用点逐点梳理**（4 个并行子智能体 + 主控覆盖基础设施文件）：修正约 25 处——意外异常的 `logger.error` 改 `logger.exception` 补堆栈（auth/crypto/article_crawler/a_share_search/market_chart/news 路由等）、降级路径 debug/info 提级 warning（stock_news_search 的 LLM/Tavily/Google 降级、market 路由 Yahoo 降级、market_chart 主源切备源、x_health_probe 按 healthy 分级）、补关键上下文（notification job id、redis stream 名、dedup 标题对、digest scope、llm cache hash 等）、消灭 f-string 插值与 `workers/news_fetcher.py` 的 2 处 print（该独立入口同时补 `configure_logging` 调用避免转 logger 后静默）、`event_bus` 函数内 import logging 上提为模块级。`ensure_exclusive_ownership(log=...)` 的可注入参数名与 `getLogger()` 取 root 属刻意设计，保留。
  7. **配套**：新增根目录 `.env.example` 记录全部日志相关环境变量（LOG_*/ACCESS_LOG_*/FRONTEND_LOG_*）；`config.py` 新增 access_log_enabled/access_log_exclude_prefixes/frontend_log_* 共 6 个配置项。
- 影响文件：新增 `backend/app/core/log_context.py`、`backend/app/core/request_logging.py`、`backend/app/api/routes/logs.py`、`backend/app/schemas/frontend_log.py`、`backend/tests/test_request_logging.py`、`backend/tests/test_frontend_log_endpoint.py`、`frontend/src/utils/logger.ts`、`frontend/src/utils/logger.test.ts`、`.env.example`；修改 `backend/app/core/logging.py`、`config.py`、`main.py`、`api/router.py`、`workers/base_worker.py`、`pipeline_worker_main.py`、`Makefile`、`docs/code-change-log.md`，以及调用点梳理涉及的 18 个后端文件与前端 11 处替换涉及的 10 个文件（全清单见 git status，共 35 改 + 9 新增）。
- 接口/数据结构变化：新增端点 `POST /api/logs/frontend`（请求 `{entries:[{level,message,stack?,url?,ts?,context?}]}`，响应 `{accepted,dropped}`）；所有 HTTP 响应新增 `X-Request-ID` 头；json 日志格式新增 `module/lineno/request_id/task_id/exc/stack` 字段（原有 `ts/level/logger/message` 不变）；无数据库变化。
- 验证情况：后端全量 `conda run -n news-caught pytest backend/tests -q` 1234 passed / 8 failed，8 个失败均为既有问题且与本次无关（7 个 test_news/test_news_analysis 顺序污染，隔离复跑 28 passed；1 个 test_news_relevance_experiment_runner 硬编码主 worktree 绝对路径，仅能在主 worktree 通过）；另外 4 个 test_a_share_search_service 失败系本 worktree 缺 gitignore 的 `backend/app/data/a_shares_dataset.json`，从主 worktree 复制后转绿。日志专项测试 36 个全过（含新增：json 堆栈保留、上下文注入、中间件 request_id 透传/清洗/排除/500 分级、上报端点截断/413/限流、initializer 不动 root handler 回归）。`ruff check backend/app backend/tests` 通过。前端 `npm --prefix frontend test -- --run` 83 文件 494 全绿（新增 logger 10 例），`npm run typecheck`（vue-tsc -p tsconfig.app.json）通过。
- 风险或后续事项：访问日志对 SSE 连接在断开时才产生记录（已默认排除 `/api/stream`）；前端上报限流为进程级内存态，多进程部署时配额按进程独立；`alembic.ini` 的 [loggers] 段保留供 alembic CLI 直跑使用（应用进程内已隔离）；uvicorn 多 worker 形态下多进程共写同一轮转文件存在竞态风险，当前单进程形态无碍，若未来多进程部署建议按进程分文件或收敛到 stdout 采集。
## 2026-08-03 LLM 分支合并审查：修复窄屏聊天页不可访问

- 修改人：Codex
- 修改范围：聊天路由 AppShell 响应式高度锁定、对应测试与设计说明。
- 变更内容：代码审查发现 `/chat` 的 `100dvh + overflow-hidden` 被无条件应用；在低于 `shell` 断点的单列布局中，侧栏和主内容各占近一屏，外层又禁止滚动，导致第二行聊天主内容不可访问。现将视口锁定、内部侧栏滚动和主区两行 Grid 约束全部限制在 `shell:` 桌面断点；窄屏保持 `min-h-screen` 正常文档流，桌面端长对话仍只滚动消息 viewport。
- 影响文件：`frontend/src/components/layout/AppShell.vue`、`frontend/src/components/layout/AppShell.test.ts`、`docs/superpowers/specs/2026-08-03-chat-inner-scroll-design.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：无。
- 验证情况：新增响应式类契约测试在旧实现下失败；修复后 `AppShell.test.ts`、`ChatView.test.ts`、`ChatMessageList.test.ts` 共 31 passed。分支全量测试和构建将在提交前继续执行。
- 风险或后续事项：窄屏继续整页滚动，桌面端继续消息区内滚动；两种布局边界由 Tailwind `shell` 断点统一控制。

## 2026-08-03 AI 对话改为消息内窗口滚动

- 修改人：Codex
- 修改范围：AppShell 聊天路由布局、ChatView 高度收缩、消息 viewport 滚动隔离、前端测试与文档
- 变更内容：修复长回答把整个页面持续向下撑高的问题。`ChatView` 根工作区改用 `100dvh` 相关固定高度并增加 `min-h-0/overflow-hidden`，右侧三行 Grid 的消息轨道显式使用 `minmax(0,1fr)`；`ChatMessageList` 外层禁止溢出，实际消息区使用 `overflow-y-auto`、`overscroll-behavior:contain` 和稳定滚动条槽位。进一步根据浏览器量测确认 AppShell 左侧导航在矮窗口也会撑高文档，因此仅在 `/chat` 路由把应用壳锁定为单视口，左侧导航必要时内部滚动，其他页面继续保持整页滚动。模型栏、底部输入框与会话新建按钮不会再被长对话顶出视口。
- 影响文件：`frontend/src/components/layout/AppShell.vue`、`frontend/src/components/layout/AppShell.test.ts`、`frontend/src/views/ChatView.vue`、`frontend/src/views/ChatView.test.ts`、`frontend/src/components/chat/ChatMessageList.vue`、`frontend/src/components/chat/ChatMessageList.test.ts`、`docs/superpowers/specs/2026-08-03-chat-inner-scroll-design.md`、`docs/superpowers/plans/2026-08-03-chat-inner-scroll-plan.md`、`docs/code-change-log.md`
- 接口/数据结构变化：无；纯前端布局行为变化，仅 `/chat` 路由的外层页面滚动改为消息区内滚动。
- 验证情况：TDD 新增用例在修改前稳定失败，分别暴露 ChatView 缺少视口约束、消息容器缺少 overflow/overscroll 约束、AppShell 未锁定聊天路由三处问题；实现后目标测试 `AppShell.test.ts + ChatView.test.ts + ChatMessageList.test.ts` 31 passed；`npm --prefix frontend test -- --run` 全量 84 files / 491 tests 通过；`npm --prefix frontend run build` 通过；`git diff --check` 通过。浏览器实测同一 743px 高窗口下，修复前 `document.scrollHeight=1470`，修复后 `document.scrollHeight=document.clientHeight=743`；消息区计算样式为 `overflow-y:auto`、`overscroll-behavior-y:contain`，输入栏保持完整可见，控制台无错误。
- 风险或后续事项：聊天路由在较矮窗口下左侧导航会出现自己的内部滚动条，这是为保持整个聊天工作区固定在一屏内的预期行为；其他路由不受影响。

## 2026-08-03 AI 对话内窗口滚动设计与计划

- 修改人：Codex
- 修改范围：AI 对话长消息滚动行为的根因分析、布局设计与 TDD 计划
- 变更内容：根据用户截图确认长回答会触发 Grid item 默认 `min-height:auto`，把聊天页与外层文档一起撑高；新增设计文档，确定仅在 `/chat` 内采用动态视口高度、`min-h-0`、`overflow-hidden` 和 `overscroll-behavior:contain` 的三层约束，使模型栏和输入栏固定、消息记录仅在内窗口滚动；新增对应测试与浏览器验收计划。
- 影响文件：`docs/superpowers/specs/2026-08-03-chat-inner-scroll-design.md`、`docs/superpowers/plans/2026-08-03-chat-inner-scroll-plan.md`、`docs/code-change-log.md`
- 接口/数据结构变化：无。
- 验证情况：设计阶段已检查 `AppShell.vue`、`ChatView.vue`、`ChatMessageList.vue` 与截图表现；纯文档阶段未运行测试或构建。
- 风险或后续事项：本次只调整聊天页，不改变其他需要整页滚动的模块。

## 2026-08-03 AI 对话流式推理展示与模型快捷预设

- 修改人：Codex
- 修改范围：LLM provider 流式协议、AI 对话消息状态与推理面板、模型设置快捷预设、测试与文档
- 变更内容：
  1. 后端 `AsyncOpenAICompatibleProvider.chat_stream` 新增 typed `reasoning` 事件，读取常见 OpenAI-compatible 流中的 `delta.reasoning_content`，并兼容字符串/简单对象形式的 `delta.reasoning`、`delta.thinking`；推理与正文都计入缺失 usage 时的 completion token 估算，也都视为首字节，避免推理已展示后对同一 provider 重试造成内容重复。`/api/llm/chat` SSE 新增独立 `{"reasoning":"..."}` 帧，已有 `text` / `failover` / `error` 帧保持兼容。
  2. 前端 `ChatMessage` 新增可选 reasoning 状态；`useChatStream` 以同一 30ms 节拍分别平滑消费推理与正文缓冲区，两个缓冲区排空后才结束 streaming 并持久化，会话历史仍只回传最终答案正文。`ChatMessageList` 新增低视觉优先级的可折叠推理面板，生成中默认展开并显示“推理中”，无 reasoning 的模型维持原普通回答界面。
  3. LLM 设置表单新增 OpenAI、Qwen/DashScope、DeepSeek、Moonshot/Kimi、SiliconFlow、Gemini 六组 OpenAI-compatible 快捷预设；点击后只填入公开的 Provider、显示名、Base URL 与推荐模型，不覆盖 API Key、价格、预算和启用状态；同时提供候选模型快捷按钮、官方文档链接和自定义模式。预设元数据抽出为独立模块并加单元测试。
- 影响文件：`backend/app/services/llm_providers.py`、`backend/app/api/routes/llm.py`、`backend/tests/test_llm_providers.py`、`backend/tests/test_llm_chat.py`、`frontend/src/composables/useChatSessions.ts`、`frontend/src/composables/useChatStream.ts`、`frontend/src/composables/useChatStream.test.ts`、`frontend/src/components/chat/ChatMessageList.vue`、`frontend/src/components/chat/ChatMessageList.test.ts`、`frontend/src/components/llm/LlmConfigForm.vue`、`frontend/src/components/llm/providerPresets.ts`、`frontend/src/components/llm/providerPresets.test.ts`、`frontend/src/views/LlmSettingsView.test.ts`、`docs/superpowers/specs/2026-08-03-llm-stream-reasoning-and-presets-design.md`、`docs/superpowers/plans/2026-08-03-llm-stream-reasoning-and-presets-plan.md`、`docs/code-change-log.md`
- 接口/数据结构变化：有，`POST /api/llm/chat` 的 SSE 流新增可选 `reasoning` JSON 帧；这是向后兼容的增量，既有只消费 `text` 的客户端无需修改。无数据库或持久化 schema 变化；前端 localStorage 消息对象可能新增可选 `reasoning` 字段，旧会话兼容。
- 验证情况：TDD 阶段后端新增测试先稳定失败（provider 丢弃 reasoning、API 将 reasoning 错当 text）；实现后 `conda run -n news-caught pytest backend/tests/test_llm_providers.py backend/tests/test_llm_chat.py -q` 69 passed；`npm --prefix frontend test -- --run` 84 files / 488 tests 全绿；`npm --prefix frontend run build` 通过；`conda run -n news-caught ruff check backend/app/services/llm_providers.py backend/app/api/routes/llm.py backend/tests/test_llm_providers.py backend/tests/test_llm_chat.py` 通过；`git diff --check` 通过。浏览器实测 Qwen 预设字段、文档链接与 API Key 保留行为正确，配置栏无横向溢出、控制台无错误。
- 风险或后续事项：只有实际返回 reasoning 字段的模型才会显示推理面板，OpenAI-compatible 服务之间字段仍可能存在未覆盖的私有变体；供应商模型名可能随时间变化，用户可随时自定义修改。`npm ci` 审计现有依赖树报告 10 个漏洞（1 moderate / 8 high / 1 critical），本次未改依赖版本且未执行可能引入破坏性升级的 `npm audit fix`，建议后续独立治理。

## 2026-08-03 AI 对话推理流与模型快捷预设设计、实现计划

- 修改人：Codex
- 修改范围：AI 对话流式推理展示、LLM 模型快捷预设的需求设计与 TDD 实施计划
- 变更内容：审查现有 `/api/llm/chat` SSE、`AsyncOpenAICompatibleProvider.chat_stream`、`useChatStream`、消息列表和 LLM 配置表单后，确认现有系统已支持正文流式回答但会丢弃 `reasoning_content`，配置页仍需逐项手填；新增设计文档，确定以独立 reasoning 事件传输模型实际返回的推理内容、前端双缓冲渐进渲染和可折叠推理面板，并以静态前端预设提供 OpenAI、Qwen/DashScope、DeepSeek、Moonshot/Kimi、SiliconFlow、Gemini OpenAI compatibility 的服务地址、推荐模型和官方文档入口；新增 TDD 实现计划，拆分后端协议、前端展示、快捷预设和验证评审四个任务。
- 影响文件：`docs/superpowers/specs/2026-08-03-llm-stream-reasoning-and-presets-design.md`、`docs/superpowers/plans/2026-08-03-llm-stream-reasoning-and-presets-plan.md`、`docs/code-change-log.md`
- 接口/数据结构变化：本条仅新增设计与计划，无运行时接口或数据结构变化；设计计划新增兼容性的 SSE `reasoning` 可选帧，不修改数据库。
- 验证情况：已基于现有代码与测试完成设计审查；纯文档阶段未运行测试或构建。
- 风险或后续事项：reasoning 字段并非所有 OpenAI-compatible 服务都提供；供应商模型名可能变化，因此预设只作为表单便利入口并保留完全自定义能力。
## 2026-08-03 Latest Events 移除警报 UI 并新增手动新闻抓取

- 修改人：Codex
- 修改范围：Latest Events 页面信息层级、AppShell 主内容布局、手动新闻抓取交互及对应前端测试。
- 变更内容：移除 Latest Events 的 Runtime 状态警报和 Raw Stream 标题说明，仅保留事件、主题、筛选与新闻流；移除 AppShell 主内容顶部的 SSE / Last event / Workspace 状态条，侧栏系统诊断继续保留；在 Latest Events 页头新增“抓取最新新闻”按钮，复用 `newsStore.refreshNews()` 和既有异步刷新接口，补充请求提交态、抓取中禁用态、成功/未启动轻量反馈及 `aria-live`；前端测试按新行为更新。
- 影响文件：`frontend/src/views/NewsFeedView.vue`、`frontend/src/views/NewsFeedView.test.ts`、`frontend/src/components/layout/AppShell.vue`、`frontend/src/components/layout/AppShell.test.ts`、`docs/code-change-log.md`。
- 接口/数据结构变化：无；继续调用现有 `POST /api/news/refresh?async_mode=true`，后端契约和数据库结构不变。
- 验证情况：TDD 红灯已确认，旧实现下两个专项测试文件共 8 个新预期失败；修改后专项测试 `npm --prefix frontend test -- --run src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts` 为 2 files / 41 tests 通过；前端全量 `npm --prefix frontend test -- --run` 为 82 files / 485 tests 通过；`npm --prefix frontend run build` 通过；`git diff --check` 通过。浏览器实测 `/news`：手动抓取按钮正常显示，Runtime 警报、Raw Stream 标题和 AppShell 顶部状态条均不存在，控制台无 error；为避免实测触发真实抓取和数据库写入，按钮请求行为由 Vitest mock 覆盖。
- 风险或后续事项：异步接口被接受后可能没有新增条目，按钮反馈仅表述“开始抓取”；store 的 `false` 返回同时覆盖冷却、失败和 mock 降级，页面统一提示稍后重试。

## 2026-08-03 Latest Events 精简警报与手动抓取设计/计划

- 修改人：Codex
- 修改范围：Latest Events 前端信息层级调整与手动新闻抓取交互设计。
- 变更内容：根据用户提供的三张截图，明确移除页面 Runtime 警报、Raw Stream 标题说明和 AppShell 顶部 SSE 状态条；设计在 Latest Events 页头复用现有异步新闻刷新接口、store 冷却和刷新状态，并补充实现计划、测试边界与验收标准。
- 影响文件：`docs/superpowers/specs/2026-08-03-latest-events-manual-refresh-design.md`、`docs/superpowers/plans/2026-08-03-latest-events-manual-refresh-plan.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：无；计划复用现有 `POST /api/news/refresh?async_mode=true`。
- 验证情况：仅文档，未运行代码测试；已对照现有 `NewsFeedView`、`AppShell`、`newsStore.refreshNews` 和后端刷新路由确认方案可落地。
- 风险或后续事项：异步接口只保证任务被接受，页面反馈不得将其表述为已抓取到新新闻；实现完成后需补充实际测试与构建结果。
## 2026-08-03 仪表盘分支合并审查与生命周期加固

- 修改人：Codex
- 修改范围：动态行情条卸载生命周期、仪表盘市场情绪设计/计划文档和测试。
- 变更内容：代码审查发现 `MarketTickerStrip` 为涨跌闪烁创建的 600ms 定时器仅在下一次同标的变化时替换，路由切换卸载组件时不会清理，仍可能回调并修改已卸载组件状态。现于 `onBeforeUnmount` 清理并清空全部闪烁计时器；新增失败测试固定该生命周期契约；补充仪表盘市场情绪与动态行情的设计及实现计划文档。
- 影响文件：`frontend/src/components/dashboard/MarketTickerStrip.vue`、`frontend/src/components/dashboard/MarketTickerStrip.test.ts`、`docs/superpowers/specs/2026-08-03-dashboard-market-sentiment-design.md`、`docs/superpowers/plans/2026-08-03-dashboard-market-sentiment-plan.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：无。
- 验证情况：卸载清理测试在旧实现下失败；修复后仪表盘三个专项测试文件共 15 passed。分支全量测试和构建将在提交前继续执行。
- 风险或后续事项：行情条的动画与闪烁均为前端展示增强，不影响行情数据刷新和缓存语义。

## 2026-08-02 仪表盘优化：市场情绪/恐慌可视化 + 动态行情条，移除来源健康区块

- 修改人：Kimi
- 修改范围：Dashboard 页面（前端），删除底部来源健康区块，接入既有 `GET /api/market/overview` 数据做市场情绪与恐慌可视化。
- 变更内容：
  1. 删除仪表盘底部"来源健康"区块：`DashboardView.vue` 移除对应 `SectionCard`、`SourceHealthGrid` import 与 `sourceHealthItems` computed（来源健康明细仍可在 `/ops` 运维页查看；`newsStore.loadNewsRuntime` 轮询有其他用途，未动）。删除 `SourceHealthGrid.vue` 及其测试（grep 确认仅 DashboardView 引用）。
  2. 新增 `components/dashboard/FearGreedPanel.vue` + `FearGreedGauge.vue`（替代原来源健康位置）：五市场恐慌贪婪仪表（quant_sentiment score [-1,1] 映射 0-100，五段色带 SVG 半圆仪表，指针 CSS transition 平滑摆动；label 中文化 极度恐慌/恐慌/中性/贪婪/极度贪婪，配色与 MarketOverviewCard 五色体系一致）；输入因子 chips（VIX / 涨跌比 / 指数均涨跌）；涨跌家数堆叠宽度条（汇总 boards.items 的 advance/decline/flat，红涨绿跌，宽度 transition）；新闻情绪分行。quant_sentiment 为 null 或板块非 ok 时优雅降级为 `--` / "数据不足"。
  3. 新增 `components/dashboard/MarketTickerStrip.vue`（位于突发新闻横幅之下）：全市场指数横向无缝滚动条（CSS marquee，列表双份渲染，悬停暂停；时长随条目数伸缩），^VIX 按既有约定不展示；watch 各指数 change_percent，数值变动时该项闪烁 600ms（上跳 --positive-soft / 下跳 --negative-soft）；不可用指数显示 `--`。
  4. `DashboardView.vue` 接线 `marketOverviewStore`：`onMounted` 首载 + `startAutoRefresh()`（60s 轮询），`onUnmounted` 停止，与 WatchlistView 同一模式；`SectionCard` import 随来源健康删除一并移除。
  5. 测试：新增 `FearGreedPanel.test.ts`（卡片渲染/label 映射/降级/涨跌条比例/空态 4 例）、`MarketTickerStrip.test.ts`（空态/双份渲染与 ^VIX 过滤/不可用占位/涨跌闪烁 4 例）；`DashboardView.test.ts` 补充 `marketOverviewStore` mock。
- 影响文件：`frontend/src/views/DashboardView.vue`、`frontend/src/views/DashboardView.test.ts`、`frontend/src/components/dashboard/FearGreedPanel.vue`（新增）、`frontend/src/components/dashboard/FearGreedGauge.vue`（新增）、`frontend/src/components/dashboard/MarketTickerStrip.vue`（新增）、`frontend/src/components/dashboard/FearGreedPanel.test.ts`（新增）、`frontend/src/components/dashboard/MarketTickerStrip.test.ts`（新增）、删除 `frontend/src/components/dashboard/SourceHealthGrid.vue` 与 `SourceHealthGrid.test.ts`、`docs/code-change-log.md`。
- 接口/数据结构变化：无。纯前端改动，消费既有 `GET /api/market/overview`（此前仅 WatchlistView 使用），无新增依赖。
- 验证情况：`npx vitest run` 全量 83 文件 489 测试全绿；`npm --prefix frontend run build`（含 vue-tsc）通过。未做浏览器手动实测。
- 风险或后续事项：kr/jp/eu 市场常态缺 VIX/涨跌家数输入，对应卡片会显示"数据不足"占位，属后端数据现状而非缺陷；行情条闪烁依赖 60s 轮询的数据变化，闭市期间数值不变则不闪烁。

## 2026-08-02 本地功能分支终审、集成修复与合并 main

- 修改人：Codex
- 修改范围：本地分支拓扑审计、`feature/market-overview` 与 `feat/sentiment-revamp` 合并、跨分支冲突和契约/迁移集成修复、合并后全量验证。
- 变更内容：
  1. 审计全部本地/远端引用与 worktree：确认 `redesign/smart-quant-desk` 已是 `main` 祖先、无需重复合并；将市场总览分支以独立 merge commit 合入 `main`，随后合入情绪评测/时间线分支。合并过程中保留双方 `docs/code-change-log.md` 内容，并让 `frontend/src/api/mock.ts` 同时导出 marketOverview、sentimentEval、sentimentTimeline 三个 mock 域。
  2. 修复合并后 Alembic 双 head：两条分支原本都从 `d4b7e1f0c3a6` 分叉，现将情绪迁移 `e6c2a9f4d1b7` 的父版本改为市场总览迁移 `e5f9a2c4b7d1`，形成 `d4b7e1f0c3a6 → e5f9a2c4b7d1 → e6c2a9f4d1b7` 单线迁移链。
  3. 按合并后的后端重新导出 `frontend/openapi.json` 并生成 `frontend/src/types/generated/api.d.ts`；情绪评测、回测 Phase 2、情绪时间线类型从临时手写结构收敛回 generated schema。对 `BacktestSummaryView` 中 Pydantic 默认字段仅在适配层放宽为可选，以兼容升级前旧响应；测试夹具补齐校准结果的 generated 必填元数据。
  4. 修复终审暴露的静态检查问题：整理情绪路由/脚本/测试 import，移除多余 UTF-8 encode 参数，并把“非法 LLM 预标注响应”测试从宽泛 `Exception` 收紧为带消息断言的 `ValueError`。
- 影响文件：合入两个功能分支的全部文件；集成修复重点涉及 `backend/alembic/versions/e6c2a9f4d1b7_add_sentiment_eval_run.py`、`backend/app/api/routes/eval.py`、`backend/scripts/annotate_sentiment_dataset.py`、`backend/scripts/run_sentiment_experiment.py`、`backend/tests/test_llm_classification_cache.py`、`backend/tests/test_sentiment_dataset_tools.py`、`frontend/openapi.json`、`frontend/src/types/generated/api.d.ts`、`frontend/src/types/api.ts`、`frontend/src/api/mock.ts`、`frontend/src/views/SignalBacktestView.test.ts`、`docs/code-change-log.md`。
- 接口/数据结构变化：合入分支带来的新增接口与表结构见其各自记录；本集成额外将 Alembic 迁移从双 head 调整为线性单 head，并把前端 OpenAPI/生成类型更新为同时包含市场总览与情绪模块的最终契约。无删除接口或破坏性数据库变更。
- 验证情况：分支差异 `git diff --check` 通过；跨分支专项后端测试 220 passed；修复后受影响后端测试 42 passed；后端全量 `pytest backend/tests -q` 为 1216 passed / 7 failed，7 个失败均为仓库已有的 `test_news.py` / `test_news_analysis.py` 测试顺序污染（固定种子新闻被前序用例清空），用全新测试库单独复跑两文件 28 passed；前端全量 `npm --prefix frontend test -- --run` 为 82 files / 484 tests 全绿；`npm --prefix frontend run build` 通过；`conda run -n news-caught ruff check backend/app backend/tests backend/scripts` 通过；OpenAPI export check 与 `check:api-drift` 通过；`alembic heads` 为单一 head `e6c2a9f4d1b7`。
- 风险或后续事项：后端全量测试仍存在已确认的新闻测试顺序污染，建议后续专项修复测试隔离；根目录未跟踪 `node_modules/` 与情绪 worktree 内未跟踪 `frontend/node_modules` 均未纳入提交。合并前已创建本地保护分支 `backup/main-before-integration-20260802` 指向原 `main`。

## 2026-08-02 C1 市场总览前后端联调：openapi 导出 + 类型生成对齐 + 全量验证与冒烟

- 修改人：Kimi
- 修改范围：OpenAPI 契约导出、前端类型生成与 `types/api.ts` 手写类型对齐、全量回归与端到端冒烟（计划任务 C1）
- 变更内容：
  1. 运行 `conda run -n news-caught python scripts/export_openapi.py` 更新 `frontend/openapi.json`（含 `/api/market/overview`、`/api/market/index-config`、`/api/market/index-config/{config_id}` 三条新路径；`--check` 复核一致），随后 `npm --prefix frontend run generate:api` 重新生成 `frontend/src/types/generated/api.d.ts`。
  2. `frontend/src/types/api.ts` 市场总览区块由手写 interface 全部改为 generated 别名（`OverviewIndexQuoteView / QuantSentimentView(+InputsView) / BoardSectionView / BoardItemView / NewsSentimentView / NewsSignalItemView / MarketOverviewMarketView / MarketOverviewView / MarketIndexConfigView / MarketIndexConfigCreateRequest / MarketIndexConfigUpdateRequest`），消除手写与后端的漂移：手写 `MarketBoardItem.name` 由必填改为 `string|null`、`MarketNewsSignalItem.signal_confidence` 由必填 number 改为可空、`canonical_url` 由可空改为必填、`QuantSentiment.inputs` 由可空改为必填——均以 generated（即后端 schema）为准。保留两类增补并注释原因：窄化联合（`MarketOverviewMarketKey / MarketIndexKind / QuantSentimentLabel / MarketBoardSource`，后端 schema 为普通 string，仅作 UI 窄化）；交叉类型恢复必填（`MarketBoardSection.items`、`MarketOverviewMarket.indices/quant_sentiment/boards/news_sentiment`、`MarketOverview.markets`，因 pydantic 默认值在 generated 中被标成可选但契约保证下发）；`MarketIndexConfigCreate` 用 `Omit+Partial<Pick>` 把后端有默认值的 kind/sort_order/enabled 放宽为可选（generated 把带默认值字段标成必填，与线上契约不符）。
  3. 必要的配套微调：`MarketOverviewCard.vue` 置信度渲染改 `(signal.signal_confidence ?? 0) * 100`（generated 中可空）；`MarketIndexConfigModal.vue` `groupedConfigs` 分组键显式标注为 `string`（generated 中 market 为普通 string，extras 兜底分支需要）；`api/mock/ops.ts` `mockHealth` 补齐 HealthResponse 新增必填字段（database_healthy/active_stream_connections/ai_status/source_health_summary）——该漂移由重新生成快照暴露，属既有后端健康检查扩展，非本功能改动。
- 影响文件：`frontend/openapi.json`、`frontend/src/types/generated/api.d.ts`、`frontend/src/types/api.ts`、`frontend/src/components/watchlist/MarketOverviewCard.vue`、`frontend/src/components/watchlist/MarketIndexConfigModal.vue`、`frontend/src/api/mock/ops.ts`、`docs/code-change-log.md`
- 接口/数据结构变化：无新增接口变化；本条目是把既有后端契约固化进 openapi.json 与前端类型。前端导出名全部保持不变，调用方无迁移成本。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news_caught_test_c1.db conda run -n news-caught pytest backend/tests -q` 1084 passed / 8 failed——8 个失败在排除全部市场总览功能文件后原样复现（961 passed），其中 7 个（test_news.py 3 个 + test_news_analysis.py 4 个）单独成组跑全部通过、属既有顺序依赖问题（同此前记录的 test_news_relevance_annotation 同类，本次该用例未复现），另 1 个 `test_a_share_search_service.py::test_search_a_shares_performance` 为耗时阈值性能用例（断言 100 次搜索 <0.3s，机器负载下单跑也会 0.51s 超时、负载低时通过），均与本功能无关；市场总览相关 11 个测试文件单独跑 123 passed。`npm --prefix frontend test -- --run` 81 文件 471 全绿；`npm --prefix frontend run build`（含 vue-tsc）通过；`conda run -n news-caught ruff check backend/app backend/tests` 全部通过。冒烟：8321 端口起 uvicorn，带 X-App-Token 请求 `GET /api/market/overview` 200（五市场骨架、us 含真实行情/量化情绪/preset_etf 板块/新闻情绪 top_signals），`GET index-config` 200、POST 201（symbol 自动大写）、重复 POST 409、PATCH 200、PATCH 带 symbol 422、DELETE 204，冒烟后已清理测试数据并关闭进程。
- 风险或后续事项：后端全量测试的顺序依赖污染（news/news_analysis 域 7 个用例）与 a_share 性能阈值抖动为既有问题，建议后续专项治理；git status 中 test_news.py、quote_service.py、watchlistStore.ts、AppShell.vue、KlineChart 等为建分支前历史未提交改动，本次未触碰，上述失败集与这些历史改动同属非本功能范围。

## 2026-08-02 F1–F5 前端市场总览区块（面板/卡片/配置弹窗/store/apiClient/mock）

- 修改人：Kimi
- 修改范围：前端市场总览 UI 与数据层（计划任务 F1–F5，由并行代理完成，本条为补录）
- 变更内容：
  1. `types/api.ts` 新增 MarketOverview 域手写契约类型（按设计文档九节，注释标明待 C1 联调以 generated 类型对齐，C1 已完成替换）。
  2. `api/client.ts` 新增五个方法：`getMarketOverview`（withMockFallback 降级）/ `getMarketIndexConfig`（同）/ `createMarketIndexConfig` / `updateMarketIndexConfig` / `deleteMarketIndexConfig`；`api/mock/marketOverview.ts` 新增五市场总览与 11 条指数配置的 mock 数据。
  3. `stores/marketOverviewStore.ts`：overview/indexConfigs 状态、加载与错误态、60s 轮询刷新、配置增删改后自动重拉总览。
  4. 组件：`MarketOverviewPanel.vue`（五市场卡片横排 + 配置弹窗入口）、`MarketOverviewCard.vue`（指数行/^VIX 过滤、量化情绪五色 chip、板块区三分支渲染、新闻情绪分数与 top_signals 点击跳新闻详情、缺数据优雅降级）、`MarketIndexConfigModal.vue`（按市场分组的配置表：启用开关、行内编辑名称/排序保存 PATCH、删除确认、底部新增表单）。
  5. `WatchlistView.vue` 顶部集成 `<MarketOverviewPanel />`。
- 影响文件：`frontend/src/types/api.ts`、`frontend/src/api/client.ts`、`frontend/src/api/mock/marketOverview.ts`（新增）、`frontend/src/stores/marketOverviewStore.ts`（新增）、`frontend/src/components/watchlist/MarketOverviewPanel.vue` / `MarketOverviewCard.vue` / `MarketIndexConfigModal.vue`（新增）、`frontend/src/views/WatchlistView.vue` 及对应测试文件
- 接口/数据结构变化：无后端变化；前端消费 `GET /api/market/overview` 与 `/api/market/index-config` CRUD（契约见 C1 条目与设计文档九节）。
- 验证情况：前端 `npm --prefix frontend test -- --run` 81 文件 471 全绿、`npm --prefix frontend run build` 通过（并行代理自测 + C1 全量复跑确认）。
- 风险或后续事项：无。

## 2026-08-02 B6+B7 市场总览 API（/api/market/overview + 配置 CRUD）与 MarketOverviewProducer 接线

- 修改人：Kimi
- 修改范围：市场总览聚合端点、指数配置 CRUD 端点、overview 轮询 worker 与 main.py 接线（计划任务 B6、B7）
- 变更内容：
  1. `schemas/market.py` 新增 Overview/IndexConfig 相关 View：`MarketOverviewView / MarketOverviewMarketView / OverviewIndexQuoteView / QuantSentimentView(+InputsView) / BoardSectionView / BoardItemView / NewsSentimentView / NewsSignalItemView / MarketIndexConfigView / MarketIndexConfigCreateRequest / MarketIndexConfigUpdateRequest`（Update 请求模型 `extra="forbid"` 且不含 symbol/market 字段，显式传入直接 422）。
  2. `api/routes/market.py` 新增 `GET /api/market/overview`：固定五市场骨架（us/cn/kr/jp/eu，含空配置市场的空 indices 骨架），组装指数快照（^VIX 不在指数行展示）+ `compute_market_sentiment` 量化情绪（cn 的涨跌家数与板块榜共用同一份东财缓存结果）+ 板块区三分支（cn=eastmoney / us,eu=preset_etf 取配置表 kind=etf 行 / kr,jp=none）+ B5 新闻情绪；读路径只查库 + 进程内缓存，不阻塞外网。新增配置 CRUD：`GET/POST /api/market/index-config`、`PATCH/DELETE /api/market/index-config/{id}`；POST 校验 market ∈ 五市场、kind ∈ {index,etf}、symbol 去空白大写非空、display_name 非空（违反 400），同 (symbol, market) 唯一冲突 409；PATCH 白名单更新 display_name/kind/sort_order/enabled；DELETE 物理删除（204）；鉴权沿用 api_router 的 verify_app_token。
  3. 新增 `services/market_overview_producer.py`：`MarketOverviewProducer`（BaseWorker 子类，`worker_name="market_overview_producer"`），`do_cycle()` = `refresh_index_quotes` 落库 + 东财板块缓存刷新（失败仅记日志不影响周期记账），`get_interval()` 盘中 60s / 全市场闭市 300s（`any_overview_market_open` 判定），不发 event_bus 事件。
  4. 新增 `workers/market_overview_producer.py` 独立进程入口（多进程部署形态，对齐 `workers/market_quote_producer.py`；因不发事件故不需要 event bus 初始化）。
  5. `main.py` 新增 `build_market_overview_producer()`，lifespan 按 `market_overview_producer_enabled` 开关启停（默认开，单机单进程形态）。
- 影响文件：`backend/app/schemas/market.py`、`backend/app/api/routes/market.py`、`backend/app/services/market_overview_producer.py`（新增）、`backend/app/workers/market_overview_producer.py`（新增）、`backend/app/main.py`、`backend/tests/test_market_overview_api.py`（新增）、`backend/tests/test_market_overview_producer.py`（新增）
- 接口/数据结构变化：新增端点 `GET /api/market/overview`、`GET/POST /api/market/index-config`、`PATCH/DELETE /api/market/index-config/{id}`（全部为新增，无既有端点变更；契约字段与设计文档九节示例逐字段对齐）；无数据库结构变化。openapi 导出与前端类型生成留待 C1 联调节点执行。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news_caught_test_b367.db conda run -n news-caught pytest backend/tests/test_market_overview_api.py backend/tests/test_market_overview_producer.py` 16 passed；全量回归（排除既有噪音 test_news/test_news_analysis/test_a_share_search_service/test_quote_batch_and_fallback）1052 passed / 1 failed，唯一失败 `test_news_relevance_annotation.py::test_annotation_service_rejects_placeholder_provider_config` 单独跑通过、排除本次新增测试文件后全量仍复现，确认为与本次无关的既有顺序依赖问题；`conda run -n news-caught ruff check backend/app backend/tests` 全部通过。
- 风险或后续事项：kr/jp/eu 新闻情绪常态 insufficient_data 属预期（设计文档六节）；指数混入 price_snapshot 后 `/api/market/snapshots` 与 ±3% 异常波动提醒会计入指数（设计已定案接受）；C1 需跑 `scripts/export_openapi.py` + 前端 `generate:api` 并手动冒烟。

## 2026-08-02 B3 MarketOverviewService：指数报价刷新与量化情绪纯函数

- 修改人：Kimi
- 修改范围：市场总览指数行情刷新服务与量化情绪计算（计划任务 B3）
- 变更内容：
  1. 新增 `services/market_overview_service.py`：`MarketOverviewService.refresh_index_quotes(session)` 读 `market_index_config`（enabled；表为空回落模块级内置默认清单 `DEFAULT_INDEX_CONFIGS`，含 ^VIX 与 kind=etf 条目）→ 直接构造 `NormalizedSymbol(symbol=原始ticker, market=配置market, provider_symbol=原始ticker)` 调 `YahooFinanceQuoteProvider.fetch_quotes_batch`（不经过 normalize_symbol，`000300.SS` 不改写 `.SH`、不路由腾讯源）→ 网络全部完成后单次写事务 `MarketRepository.save_snapshot` 批量 flush + commit（两阶段纪律，provider 失败行不回写）；`list_index_quotes(session)` 配置 join `price_snapshot` 最新快照（无快照条目 status="unavailable" 占位）。模块常量：`VIX_SYMBOL="^VIX"`、`OVERVIEW_MARKETS`、`MARKET_DISPLAY_NAMES`。
  2. `services/market_sentiment_service.py` 追加量化情绪部分（与 B5 新闻情绪共存，未改动已有代码）：`SentimentIndexQuote / BoardStats / QuantSentiment` dataclass 与纯函数 `compute_market_sentiment(indices, vix, board_stats)`——权重 指数动量 0.6 / VIX 0.25 / 涨跌家数 0.15，缺输入按剩余输入重新归一、全缺返回 `label="unknown"`；分段按"区间右端点取值 + 区间内线性插值 + 段外钳制"实现（动量 [-2,-0.5]→[-1,-0.5]、[-0.5,+0.5]→[-0.5,0]、[+0.5,+2]→[0,+0.5]，≤-2→-1、≥+2→+1；VIX [13,20]→[+0.5,0]、[20,30]→[0,-0.5]，<13→+0.5、≥30→-1；adv_ratio [0.3,0.7]→[-0.5,+0.5] 外钳 ±0.5）；标签阈值 ≤-0.6 panic / ≤-0.2 fear / ≤+0.2 neutral / ≤+0.6 greed / >+0.6 greed_extreme，阈值与权重为模块常量（设计文档七节约定不进配置表）。
- 影响文件：`backend/app/services/market_overview_service.py`（新增）、`backend/app/services/market_sentiment_service.py`（追加量化情绪部分）、`backend/tests/test_market_overview_service.py`（新增）、`backend/tests/test_market_sentiment_service.py`（追加量化情绪用例）
- 接口/数据结构变化：无 API/表结构变化；price_snapshot 开始写入指数/ETF 快照（symbol 为 Yahoo 原始 ticker，market ∈ us/cn/kr/jp/eu，既有表兼容）。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news_caught_test_b367.db conda run -n news-caught pytest backend/tests/test_market_overview_service.py backend/tests/test_market_sentiment_service.py` 37 passed（含两阶段纪律、默认清单回落、失败行不回写、量化情绪全分支边界）。
- 风险或后续事项：量化分段规则按设计文档字面实现，≥+2/+2 端点存在设计原文的跳变（+0.5→+1），如需平滑后续调参改模块常量即可；yfinance 对日韩欧指数批量下载的实测可用性留待 C1 冒烟确认。

## 2026-08-02 B5 新闻情绪按市场聚合服务

- 修改人：Kimi
- 修改范围：市场总览新闻情绪聚合（计划任务 B5）
- 变更内容：新增 `services/market_sentiment_service.py`：三级归属（`news_stock_mention` 市场集中度 ≥60% 优先 → `news_item.market` 兜底 → 不归属；hk 并入 cn，未映射市场不归属）+ `aggregate_news_sentiment(session, market)` / `aggregate_all_markets(session)`（五市场共享窗口数据一次查询）；滚动 24h 窗口（不按自然日/时区切割，`news_item.effective_at` 过滤）；单条分数 `sentiment_score` 优先、缺则回退 `news_analysis_result.sentiment` 标签映射（positive→+1/neutral→0/negative→-1），两者皆无不计入样本；样本 <3 返回 `status="insufficient_data", score=None`；top_signals 取窗口内 `news_signal_result` join `news_item` 按 `signal_confidence` 降序前 5（news_id/title/summary/signal_confidence/source_name/published_at/canonical_url，样本不足时仍返回）。
- 影响文件：`backend/app/services/market_sentiment_service.py`（新增）、`backend/tests/test_market_sentiment_service.py`（新增）
- 接口/数据结构变化：无（服务层新增，供 B6 overview 端点消费）。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news_caught_test_b367.db conda run -n news-caught pytest backend/tests/test_market_sentiment_service.py` 通过（归属三级路径、hk→cn 合并、分数回退、样本不足、top_signals 排序截断等 16 用例；该文件后又被 B3 追加量化情绪用例，合计 37 passed）。
- 风险或后续事项：现有 ingestion 源几乎无日韩欧本地语新闻，kr/jp/eu 新闻情绪常态 insufficient_data 属预期行为（设计文档六节局限，前端需优雅降级）。

## 2026-08-02 B4 EastMoneyBoardProvider 与板块进程内缓存

- 修改人：Kimi
- 修改范围：东方财富行业板块行情数据源（计划任务 B4）
- 变更内容：新增 `services/board_provider.py`：`BoardQuote` dataclass（code/name/price/change_percent/advance_count/decline_count/flat_count/net_inflow/fetched_at，映射东财 f12/f14/f2/f3/f104/f105/f106/f62）+ `EastMoneyBoardProvider.fetch_industry_boards(limit=20)`（push2 clist 接口 `fs=m:90+t:2` 行业板块、按涨跌幅降序；复用 `http_pool.get_feed_client()`，Referer 头 + 5s 超时；防御性解析，单条字段异常容错为 None、缺 f12 跳过，data/diff 结构缺失抛 RuntimeError 视为整体失败）+ 模块级 TTL 进程内缓存 `get_cached_industry_boards`（Lock + cached_at，TTL 常量 `MARKET_BOARD_CACHE_TTL_SECONDS=60` 同配置项默认值；抓取失败返回旧缓存标 `stale=True`，无缓存返回空列表 + `status="fetch_failed"`，不向外抛异常）+ 测试用 `clear_board_cache()`。板块榜单不落 price_snapshot（设计文档五节）。
- 影响文件：`backend/app/services/board_provider.py`（新增）、`backend/tests/test_board_provider.py`（新增）
- 接口/数据结构变化：无（新增进程内数据源，无表结构变化）。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news_caught_test_b367b.db conda run -n news-caught pytest backend/tests/test_board_provider.py` 通过（mock httpx：正常解析、字段缺失容错、结构异常、HTTP 失败降级 stale、无缓存 fetch_failed、TTL 命中）。
- 风险或后续事项：东财为非官方接口，字段可能静默变化或被限流，已按设计做防御性解析 + stale 降级；实测字段与限流表现留待 C1 冒烟确认。

## 2026-08-02 B2 市场总览配置项与 market_hours 五市场时段扩展

- 修改人：Kimi
- 修改范围：overview 轮询/缓存配置项与交易时段判断扩展（计划任务 B2）
- 变更内容：`core/config.py` 新增 `market_overview_producer_enabled`(True) / `market_overview_poll_interval_seconds`(60.0) / `market_overview_idle_poll_interval_seconds`(300.0) / `market_board_cache_ttl_seconds`(60) / `market_overview_news_lookback_hours`(24)；`services/market_hours.py` 新增 `_OVERVIEW_SESSIONS_UTC`（kr 00:00-06:30、jp 00:00-06:00、eu 07:30-16:30 UTC，cn/hk/us 复用现有时段）+ `is_overview_market_open(market, now=None)`（未知市场返回 False，与 `is_market_open` 的"未知按开市"语义刻意不同）+ `any_overview_market_open(now=None)`；不改 `_SESSIONS_UTC` 与既有 `is_market_open`/`any_market_open` 语义（自选股 producer 降频行为不变）。
- 影响文件：`backend/app/core/config.py`、`backend/app/services/market_hours.py`、`backend/tests/test_market_overview_config.py`（新增）、`backend/tests/test_market_hours.py`（增补）
- 接口/数据结构变化：新增 5 个配置项（环境变量同名大写可覆盖）；无表结构变化。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news_caught_test_b367b.db conda run -n news-caught pytest backend/tests/test_market_hours.py backend/tests/test_market_overview_config.py` 通过（kr/jp/eu 时段边界、any_overview_market_open、既有 cn/hk/us 回归、配置默认值与环境变量覆盖）。
- 风险或后续事项：时段判断保持粗粒度（无节假日日历、DST 取并集），错判代价仅为闭市时多轮询几次（设计文档一节接受）。

## 2026-08-02 B1 market_index_config 数据模型、Alembic 迁移与 Repository

- 修改人：Kimi
- 修改范围：市场总览指数配置表（计划任务 B1）
- 变更内容：新增 `models/market_index_config.py`（id/symbol/market/display_name/kind/sort_order/enabled + created_at/updated_at，`UniqueConstraint(symbol, market)`，索引 `(market, enabled, sort_order)`；symbol 存 Yahoo 原始 ticker 不经过 normalize_symbol）；新增 Alembic 迁移建表 + 索引（不 seed 数据，默认清单由应用层在表为空时回落）；新增 `repositories/market_overview_repository.py`（list_all/list_enabled 按 (market, sort_order) 排序、get/create/update/delete；update 字段白名单 display_name/kind/sort_order/enabled，repository 层无 symbol/market 修改入口）；顺带确认 data_cleanup 对 price_snapshot 的清理按表级时间窗执行、不区分 symbol，指数快照自然被覆盖（设计文档十三.3 定案事项）。
- 影响文件：`backend/app/models/market_index_config.py`（新增）、`backend/alembic/versions/`（新增一个 revision）、`backend/app/repositories/market_overview_repository.py`（新增）、`backend/tests/test_market_index_config_repository.py`（新增）
- 接口/数据结构变化：新增表 `market_index_config`（新表，无既有数据兼容问题）；无 API 变化。
- 验证情况：`NEWS_CAUGHT_TEST_DB=/tmp/news_caught_test_b367b.db conda run -n news-caught pytest backend/tests/test_market_index_config_repository.py` 通过（CRUD 全链路、唯一约束 IntegrityError、list_enabled 排序与过滤、update 白名单）。
- 风险或后续事项：迁移未 seed 数据，全新部署由 B3 的 MarketOverviewService 回落内置默认清单保证开箱可用。

## 2026-08-02 市场总览设计定案与实现计划

- 修改人：Kimi
- 修改范围：市场总览（Market Overview）设计文档开放问题定案 + 新增实现计划文档
- 变更内容：
  1. 设计文档三个开放问题按用户评审结论定案并补记：`^VIX` 作为美股默认配置项入 `market_index_config`（kind=index，代码按 `^VIX` 常量识别其情绪计算角色）；美/欧板块 ETF 清单入表（kind=etf）与指数统一 CRUD；指数落入 `price_snapshot` 后被 `/api/market/snapshots` 与 ±3% 异常波动提醒计入——接受；新闻情绪"当日"窗口定为滚动 24 小时（`market_overview_news_lookback_hours`）。
  2. 新增实现计划文档：按 TDD 拆分 B1–B7 后端任务（配置表迁移与 CRUD → 指数报价+量化情绪 → 东财板块 provider → 新闻情绪聚合 → overview 聚合端点 → worker 接线）与 F1–F5 前端任务（apiClient/mock → store → 卡片 → 面板集成 → 配置弹窗），两条线并行，C1 联调节点做 export_openapi + generate:api + 全量测试 + build + 手动冒烟；每个任务写明改动文件、先写的失败测试与验收命令。
- 影响文件：`docs/superpowers/specs/2026-08-02-market-overview-design.md`（开放问题节定案）、`docs/superpowers/plans/2026-08-02-market-overview-plan.md`（新增）、`docs/code-change-log.md`
- 接口/数据结构变化：无（仅文档；规划中契约以设计文档为准，实现阶段生效）
- 验证情况：仅文档，未验证（未运行测试/构建）
- 风险或后续事项：实施时东财接口字段与 yfinance 对日韩欧指数批量下载可用性需实测确认（计划文档已给出降级预案）；各任务完成后须按 AGENTS.md 规范逐条追加 change log。

## 2026-08-02 新增市场总览（Market Overview）设计文档

- 修改人：Kimi
- 修改范围：新增市场总览设计文档（Watchlist 页顶部全球大盘+情绪区块）
- 变更内容：基于对现有行情子系统（quote_provider/quote_service/market 路由/price_snapshot/market_hours）与新闻分析管线（news_item/news_analysis_result/news_signal_result/news_stock_mention）的实际代码调研，产出设计文档。关键调研结论：指数 ticker（^GSPC 等）无法通过现有 `normalize_symbol`（`^` 非字母数字抛 ValueError），设计为 overview service 直接构造 `NormalizedSymbol` 走 `YahooFinanceQuoteProvider.fetch_quotes_batch` 并复用 `price_snapshot` 落库；东财板块接口（push2.eastmoney.com clist）作为独立 provider 进程内缓存、不落 price_snapshot；新闻情绪归属利用现成的 `news_stock_mention.market` 与 `news_item.market` 字段做三级映射。文档覆盖：目标与边界、整体架构、`market_index_config` 新表与 Alembic 要点、`/api/market/overview` 与配置 CRUD 契约、东财接入与降级、量化/新闻情绪计算规则、独立低频 worker（MarketOverviewProducer）设计、前端组件拆分、测试策略与分阶段实施。
- 影响文件：`docs/superpowers/specs/2026-08-02-market-overview-design.md`（新增）、`docs/code-change-log.md`
- 接口/数据结构变化：无（仅设计文档；文档中规划的新表 `market_index_config` 与新增端点尚未实现）
- 验证情况：仅文档，未验证（设计中的代码结论均来自对相关源文件的直接阅读；未运行测试/构建）
- 风险或后续事项：东财为非官方接口（字段/限流风险）；Yahoo 对日韩欧指数有延迟；kr/jp/eu 新闻源缺失导致其新闻情绪常态无数据；^VIX 是否入配置表、美/欧板块 ETF 是否入表等开放问题待评审确认。

## 2026-08-02 16:32 修复并完善模型设置表单提交

- 修改人：Codex
- 修改范围：LLM 模型配置表单稳定性、前端校验与编辑提示
- 变更内容：修复截图中的 `raw.trim is not a function`：Vue 的 `type="number"` 输入会产生 `number`，原成本/预算转换函数却只按字符串调用 `trim()`，导致保存前同步抛错并触发整页错误边界。数字归一化现兼容字符串、数字和空值，并拒绝非有限值与负数；新增 Base URL 的 http/https 完整地址校验、字段 `aria-invalid` 状态和就地错误提示；编辑已有配置时记录原始 Base URL，地址不变可留空 API Key 并保留原 Key，地址变化则在前端明确要求重新输入明文 Key，与后端安全约束一致；无效表单会禁用保存并通过按钮 title 说明首个阻塞原因。
- 影响文件：`frontend/src/components/llm/LlmConfigForm.vue`、`frontend/src/views/LlmSettingsView.test.ts`、`docs/superpowers/specs/2026-08-02-llm-settings-form-hardening-design.md`、`docs/superpowers/plans/2026-08-02-llm-settings-form-hardening-plan.md`、`docs/code-change-log.md`。
- 接口/数据结构变化：无 API 契约或数据库结构变化；提交的成本和预算字段仍为 `number | null`，API Key 省略语义保持不变。
- 验证情况：TDD 回归用例在修复前稳定失败并捕获同样的 `TypeError: raw.trim is not a function`；修复后目标用例 7 passed。`npm --prefix frontend test -- --run` 全量通过（78 files / 429 tests）；`npm --prefix frontend run build` 通过；`conda run -n news-caught pytest backend/tests/test_llm_config.py` 通过（6 passed）；`git diff --check` 通过。浏览器实测编辑现有配置并填写数字字段后页面无控制台错误；输入非法 Base URL 时展示地址错误及重新输入 API Key 提示，更新按钮正确禁用，未提交也未修改现有配置数据。
- 风险或后续事项：本次没有在保存动作中自动请求外部模型测试连接，仍由现有“测速/测试默认连接”按钮显式触发，避免保存配置时产生额外外部调用。

## 2026-08-02 16:29 移除仓库对 Superpowers 套件的强制依赖

- 修改人：Codex
- 修改范围：仓库级智能体协作与开发流程约束
- 变更内容：将开发流程从依赖 Superpowers skills 的调用规则改为可由 Codex 或人工协作者直接执行的工程规范；删除安装、加载和修复 Superpowers 套件的前置要求；保留需求设计、实现计划、TDD、系统化调试、完成前验证、代码评审、子智能体和 git worktree 等原则，但不再绑定任何特定 skill、插件或工具包。`docs/superpowers/` 暂作为历史兼容目录名保留，并明确其不代表运行时依赖。
- 影响文件：`AGENTS.md`、`docs/code-change-log.md`
- 接口/数据结构变化：无。
- 验证情况：已检查 `AGENTS.md`，确认不再包含 Superpowers skills 安装或可用性要求；未运行代码测试（纯流程文档修改，无运行时行为变化）。
- 风险或后续事项：历史设计和计划文件仍位于 `docs/superpowers/`，目录名可能产生语义歧义；如后续需要统一命名，可另行迁移并修正引用。
