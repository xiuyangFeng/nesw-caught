# 量化工作台优化全流程实施计划（Phase A～D）

- 日期：2026-08-20
- 状态：待实施
- 对应设计：[docs/superpowers/specs/2026-08-20-quant-desk-optimization-design.md](../specs/2026-08-20-quant-desk-optimization-design.md)
- 前置：`docs/current-state.md`、根目录 `README.md`、变更记录顶部条目（无冲突）
- 交付形态：四期各自独立提交、独立回填变更记录；A/B 可并行（先冻结 §1 接口契约）；C 依赖 B 的 worker 可复用件；D 独立可最后做

## 总目标

量化工作台从「Phase 0 骨架」升级为「可直接使用的本地量化工具」：前端无裸 JSON，回测/模拟盘跑真实数据，每个交易日自动出结果，基本面 sleeve 有真实财务数据支撑。

## 全局验收（四期全部合入后）

1. 活服务端到端实测：回填若干真实标的 → 策略工作台构建器建策略 → 送回测出真实净值曲线与交易明细 → 提案一键下单模拟盘按真实价成交 → 手动触发一次调度任务验证「增量回填 + 自动跑流水线 + 通知」链路。
2. `conda run -n news-caught pytest backend/tests`（量化相关套件全绿，基线 7 个 news 顺序污染失败不计入）；`npm --prefix frontend run test`、`npm --prefix frontend run build`、`check:api-drift` 全部通过。
3. 前端页面 grep 复查：`/desk` 系列模板中不再有 `JSON.stringify` 直出、不再有未翻译的 reason_code/stage/gap 机器码上屏（运行中心 hash 除外）。

---

## §0 接口契约冻结（先做，约半小时）

在改任何实现之前，先把以下 schema 定稿并写入本节，A/B 两期据此并行：

**新增端点**
- `PATCH /api/quant/strategies/{id}`：body `{name?, dsl?, is_active?}` → 200 更新后的策略（exploratory 恒为 true，不可改为 qualified）
- `DELETE /api/quant/strategies/{id}`：204
- `POST /api/quant/portfolio-proposals/latest/execute`：body `{}` → `{orders: [{symbol, sleeve, weight, shares, filled, fill_price, reject_reason?}], cash_weight}`（shares 为 100 股整数倍）

**扩展端点**
- `POST /api/quant/backtests` 请求体增加 `symbol: str`、`start_date?: date`、`end_date?: date`；响应 `report` 增加：
  - `equity_curve: [{date, equity}]`（每持仓变动点 + 首尾点）
  - `trades: [{signal_date, entry_date, entry_price, exit_date?, exit_price?, pnl?}]`
  - `bars_used: int`、`coverage_error?: string`（bar 数不足时 200 返回该字段而非 500）
- `POST /api/quant/paper/orders` 行为变更：撮合价改为真实价（实时快照优先，最新 `daily_bar` 兜底）；无行情 200 返回 `filled=false, reason="no_market_data"`。

**治理不变项**：回测结果恒 `exploratory=true, qualified=false`；LLM 与激活策略均不改排名/仓位；`GET /api/quant/factors` 返回的因子注册表是 DSL 构建器唯一因子来源。

任务：把上述契约同步进 `frontend/openapi.json` 类型与 `frontend/src/types/api.ts`（或由后端 schema 变更后重新生成）。

---

## Phase A：前端重构 + 回测真实化

### 目标
前端不再向用户展示裸 JSON/机器码；回测实验室用真实行情库出图形化报告。

### 范围
**做**：枚举翻译层、DSL 结构化条件构建器、回测报告图形化、回测真实化（真实 bars + 真实特征）、证据链接化、机会卡展开态。
**不做**：策略编辑/删除/送回测（B）、模拟盘真实价（B）、调度 worker（C）、财务数据（D）。

### TDD 任务（先写失败测试）

后端（`backend/tests/quant/`）：
1. `test_backtest_real.py`：
   - fixture 写入真实结构 bars（≥120 根）+ `fund_flow_daily` 到测试行情库 → `run_backtest` 返回 `bars_used == len(bars)`、`equity_curve` 首点 1.0、非空 `trades`；
   - bar 数不足 → 返回 `coverage_error`，不含合成数据痕迹；
   - `walk_forward` 扩展：`equity_curve` 记录每次平仓后净值点、`trades` 含完整开平仓字段；T+1 次日开盘成交、涨跌停不可成交路径回归。
2. 特征计算单测：`features_by_date` 由真实 `fund_flow_daily`（`main_inflow_1d`）与滚动 20 日均成交额（`adv`）计算，日期对齐无前视。

前端（`frontend/src/**`）：
3. `constants/quantLabels.test.ts`：全部枚举/机器码 key 都有中文映射，缺 key 时兜底返回原码并 console.warn。
4. `components/quant/StrategyBuilder.test.ts`：因子下拉来自 factors 接口数据；增删条件行；AND/OR 切换；产出 DSL 对象与高级模式 JSON 双向同步（编辑 JSON 回填构建器）。
5. `components/quant/EquityCurveChart.test.ts`：给定曲线数据渲染 SVG path；数据点 >500 时降采样。
6. `views/DeskBacktestView.test.ts`：报告区域渲染指标卡片与曲线组件而非 `<pre>` JSON；`coverage_error` 展示引导文案。

### 实现要点
- `backend/app/services/quant_desk_service.py::run_backtest` 重写：从 `market_data.db` 按 `symbol` + 区间读 `daily_bar`，组装 `features_by_date`，调 `walk_forward`；删除 SYN 合成 bars 与硬编码特征字典。
- `backend/app/services/quant/backtest_engine.py::walk_forward` 返回值扩展（equity_curve/trades），保持纯函数。
- 新增 `frontend/src/constants/quantLabels.ts`（sleeve/horizon/state/grade/run_status/reason_code/stage/gap/board 映射）。
- 新增 `frontend/src/components/quant/StrategyBuilder.vue`、`EquityCurveChart.vue`（复用 Token Trend Chart 自绘折线范式）。
- `DeskStrategiesView.vue` / `DeskBacktestView.vue` 接入 StrategyBuilder；`DeskStockView.vue` 证据 id → `/news/:id` router-link；`DeskView.vue` 机会卡展开态展示 `factor_breakdown`（翻译后）。

### 影响文件
`backend/app/services/quant_desk_service.py`、`backend/app/services/quant/backtest_engine.py`、`backend/app/api/routes/quant.py`、`backend/app/schemas/quant.py`、`frontend/openapi.json`、`frontend/src/{constants,components/quant,views,api,types}` 相关文件、两侧测试目录。

### 验收 gate
- §0 契约端点全部按新 schema 返回；`pytest backend/tests/quant` 全绿；前端新增/改动测试全绿；`npm run build` + `check:api-drift` 通过。
- 活服务实测：对已回填 symbol 跑回测，曲线与交易数非空且随 DSL 阈值变化。

---

## Phase B：策略/提案/模拟盘闭环 + 成绩单真实窗口

### 目标
策略可管理、提案可执行、模拟盘真实价、成绩单窗口真实聚合。

### 范围
**做**：策略 PATCH/DELETE + 前端编辑/删除/送回测；提案一键转模拟盘；模拟盘真实价撮合；成绩单窗口聚合。
**不做**：调度 worker（C）、财务（D）、策略晋级治理。

### TDD 任务
后端：
1. `test_strategy_lifecycle.py`：PATCH 改名/改 DSL/切换 is_active；DELETE 后 GET 列表消失；尝试置 `exploratory=false` 被拒（422）。
2. `test_proposal_execute.py`：无提案 → 404；有提案 → 按 100 股整数倍换算 shares、逐条创建 paper order、返回逐条成交/拒单；现金仓位不下单；幂等（同提案重复 execute 返回已执行结果或明确拒绝）。
3. `test_paper_real_fill.py`：实时快照命中 → 快照价成交；仅 `daily_bar` → 最新 bar 收盘价成交；无任何行情 → `filled=false, reason=no_market_data`；涨跌停 bar 拒单路径。
4. `test_report_card_window.py`：构造跨多日的 runs，7d/30d/90d 计数随窗口真实变化；无 run 窗口返回空而非回退最新。

前端：
5. `DeskStrategiesView.test.ts`：列表行内编辑（回填构建器）、删除确认、送回测跳转带 DSL 预载（query 或 store 传递）。
6. `DeskProposalView.test.ts`：一键下单确认弹窗逐条列 symbol/股数；提交后 toast + 跳转模拟盘。
7. `DeskReportCardView.test.ts`：窗口切换触发重新请求且 URL/状态同步。

### 实现要点
- `quant.py` 路由 + `quant_desk_service.py`：`update_strategy`/`delete_strategy`/`execute_proposal`/`get_report_card`（按 run 时间窗过滤聚合）。
- 撮合价格源顺序：`price_snapshot`（自选股 producer 最近快照）→ `daily_bar` 最新收盘 → 拒单。
- 前端 `client.ts` 增 `updateQuantStrategy`/`deleteQuantStrategy`/`executeQuantProposal`；`PortfolioView.vue` 用翻译层渲染 `lastOrder.reason`。

### 验收 gate
- 契约端点全绿；活服务实测：建策略 → 编辑 → 送回测；生成提案 → 一键下单 → 模拟盘持仓出现真实价成交记录；成绩单切窗口数字变化。

---

## Phase C：每日自动化 + 运行中心增强

### 目标
交易日盘后自动「增量回填当日数据 + 跑流水线 + 通知」，零手动操作。

### 范围
**做**：`quant_scheduler_worker`、lifespan 集成、运行中心 trigger=`scheduled` 展示、数据健康增强（最新交易日缺口与最近回填错误）、手动触发端点。
**不做**：全量回填 UI、财务增量（D 期再挂进同一调度）。

### TDD 任务
1. `test_scheduler_worker.py`：
   - 交易日历判定：非交易日不触发；触发时刻可注入（fake clock）；
   - 增量回填：仅对已覆盖 symbol 抓当日 bar/资金流，失败退避不阻塞流水线；
   - 跑流水线 `scenario=real` 落 run（trigger=`scheduled`），run 状态机幂等不重复；
   - 事件发布 + 通知调用（mock 断言）。
2. `test_quant_api.py` 增：`POST /api/quant/scheduler/run`（手动触发一次当日任务，供验收与兜底）。
3. 前端 `DeskOpsView.test.ts`：Runs 列表 trigger 徽章区分 scheduled/manual；数据健康 Tab 显示最新交易日覆盖率与最近错误。

### 实现要点
- 新增 `backend/app/workers/quant_scheduler_worker.py`，复用 `base_worker.py` 心跳/状态范式与 `news_scheduler.py` 的调度形态。
- `QUANT_SCHEDULER_ENABLED`（默认 true，单进程随 lifespan 启停）、`QUANT_SCHEDULER_RUN_AT`（默认 `16:30`）环境变量，写入 README。
- 运行状态接入 `/api/stream/status`（worker_runtime_status 表）。
- 增量回填复用 `market_data/backfill.py` 的 upsert 与退避重试，只拉当日窗口。

### 验收 gate
- fake clock 单测全绿；活服务实测 `POST /api/quant/scheduler/run` 完整链路一次；`/api/stream/status` 可见 worker 心跳。

---

## Phase D：财务数据 + 基本面 sleeve 实装

### 目标
东财财务报表入库（PIT），基本面 sleeve 从永久空缺变为真实打分，研究包缺口随覆盖填充。

### 范围
**做**：东财财务采集器 + fixture 测试、`market_data.db` 新表 `financial_fact` + 迁移、回填 CLI 挂财务、调度增量挂财务、`score_fundamental` 实装、因子注册表扩展、研究包填充。
**不做**：一致预期数据、财务修订历史深挖、基本面 sleeve 晋级 qualified 的阈值治理（先只产 WATCH/候选）。

### TDD 任务
1. `test_financials_parser.py`：东财财务接口响应 fixture → 结构化指标（营收、归母净利、ROE、毛利率，按报告期）；异常/改版响应显式报错不静默。
2. `test_financial_fact_repo.py`：按 (symbol, period_end, metric_key) 幂等 upsert；`available_at` 取披露日。
3. `test_fundamental_score.py`：有数据时按净利同比/营收同比/ROE 给分并产出候选（state 至多 WATCH）；数据缺失时维持 `fundamental_gap_no_financials`，不编造。
4. `test_market_pipeline.py` 增：fundamental sleeve 用真实财务表打分的集成路径；PIT 断言（回测/打分只用 `available_at <= 截点` 的期数）。
5. 研究包测试：财务覆盖后 `no_financials` 缺口消失，填充基础问答。

### 实现要点
- 新增 `backend/app/services/quant/market_data/eastmoney_financials.py`；`alembic_market/` 新迁移建 `financial_fact` 表（不动主库）。
- `backfill_main.py` 与 Phase C 调度任务增加财务增量（新报告期才抓）。
- `factors.py::score_fundamental` 实装 + `FACTOR_REGISTRY` 增加财务因子（供 DSL 构建器自动出现）。

### 验收 gate
- fixture 单测全绿（不打真网）；活服务实测对少量 symbol 抓真实财务 → 流水线 fundamental sleeve 产出 WATCH 候选 → 研究包缺口填充。

---

## 执行顺序与并行策略

```
§0 契约冻结 ──┬── Phase A（前端重构 + 回测真实化）
              └── Phase B（闭环，前后端可并行开发）
Phase B 合入 ── Phase C（调度 worker 复用 B 的撮合/回填件）
Phase D 独立，最后做（依赖 C 的调度增量入口）
```

每期完成后：更新 `docs/code-change-log.md`、必要时更新 `docs/current-state.md`；A～D 全部合入后把本计划与设计稿一起归档到 `docs/archive/superpowers/`。

## 风险与回滚

- 各期独立提交，单期失败 `git revert` 不影响其他期（§0 契约冻结保证 schema 前向兼容，新增字段均向后兼容）。
- 东财财务接口改版：解析器 fixture 化，失败显式 gap，不阻塞 A/B/C 已交付能力。
- 调度与手动重跑并发：复用 run result_hash 幂等；调度 run 落 trigger=`scheduled` 可与手动区分审计。
- 长区间净值曲线渲染：>500 点降采样；后端 `equity_curve` 本身全量返回。
