# 量化工作台优化设计（前端重构 + 功能闭环 + 每日自动化 + 财务数据）

- 日期：2026-08-20
- 状态：已确认（2026-08-20 用户确认范围，实施计划见 `docs/superpowers/plans/2026-08-20-quant-desk-optimization-plan.md`）
- 范围：`/desk` 全系列页面、量化内核 service 层、新增 quant 调度 worker、财务数据采集
- 明确不在本期范围：LLM 参与排名或仓位（维持"LLM 不改排名/仓位"原则不变）、策略晋级为 qualified 的治理流程、退市股全量历史补齐

## 1. 背景与问题清单

现状代码能力见 `docs/current-state.md`。本轮经与用户头脑风暴确认的问题：

### 1.1 前端"裸 JSON"
| 位置 | 问题 |
|------|------|
| `DeskBacktestView.vue:64` | 回测指标整包 `JSON.stringify` 倾倒在 `<pre>`，无图无格式化 |
| `DeskStrategiesView.vue:138-142`、`DeskBacktestView.vue:43-47` | DSL 编辑是裸 JSON textarea，用户手写 JSON |
| 全线页面 | 后端枚举/机器码直接上屏：`evidence_grade`、`reason_code`、`universe_u2`、`no_financials`、`result_hash` 等 |
| `DeskStockView.vue:119` | 证据 `news-<id>` 原样显示，不可点击 |

### 1.2 功能不可用
1. **回测是合成数据**：`QuantDeskService.run_backtest`（`quant_desk_service.py:444-455`）喂 3 根硬编码 Bar + 硬编码特征字典给 `walk_forward`，从未使用 `market_data.db`。
2. **模拟盘撮合价是假的**：`place_paper_order`（`quant_desk_service.py:493-500`）对任意股票按硬编码 Bar（10 元）成交。
3. **无自动化**：回填只能 CLI（默认 100/6141 只）；流水线无每日 worker，只能手动重跑。
4. **策略是死胡同**：不能激活/编辑/删除；策略列表与回测页不通。
5. **提案只读**：无"提案→模拟盘"执行路径。
6. **成绩单窗口是摆设**：`window` 参数原样弹回，只统计最新一次 run。
7. **基本面 sleeve 永远为空**：无财务数据，`score_fundamental` 是 stub。
8. 一批后端接口前端未接（research refresh、symbol events、AI role-bindings、copilot tools）。

### 1.3 有利条件
- `walk_forward` 回测引擎本身是真的：T+1 次日开盘成交、板块涨跌停、停牌拒单（`fills.py`）都在，只差真实数据输入。
- `FinancialFact` 契约（`contracts.py:64-71`）已预埋，财务数据有 PIT 落点。
- 行情库已有 `daily_bar` / `fund_flow_daily` / `trade_calendar` 表与东财解析器；`base_worker.py` + `news_scheduler.py` 提供了 worker 与调度范式。
- 前端已有成熟的 Terminal 暗色设计语言（Dashboard、Toaster、自绘 SVG 折线），可直接复用。

## 2. 用户确认的决策

1. 范围：前端重构 + 功能闭环，一起做，分批交付。
2. 每日自动化：做（盘后自动增量回填 + 自动跑选票流水线）。
3. DSL 编辑：结构化条件构建器，JSON 作为高级模式折叠保留。
4. 基本面数据：本轮一起补（东财财务报表源）。

## 3. 方案设计

### 3.1 前端信息架构重构

**F1 枚举翻译层（新 `frontend/src/constants/quantLabels.ts`）**
- 统一映射：sleeve / horizon / candidate state / evidence grade / run status / reason_code / stage 名 / gap 码 / board → 中文人话。
- 覆盖 DeskView、DeskOpsView、DeskProposalView、DeskStockView、PortfolioView 的所有裸码输出点。
- `result_hash` 只在运行中心保留（运维语义），机会雷达页移除。

**F2 DSL 结构化条件构建器（新 `frontend/src/components/quant/StrategyBuilder.vue`）**
- 三段式：因子选择（数据源 `GET /api/quant/factors`）→ 运算符（`>`/`>=`/`<`/`<=`/区间）→ 阈值输入；多条件块 AND/OR 组合，支持增删行。
- 构建器产出合法 DSL 对象双向绑定；"高级模式"折叠区可查看/编辑 JSON（进阶用户逃生口）。
- 策略工作台与回测实验室共用该组件。

**F3 回测报告图形化（重构 `DeskBacktestView.vue`）**
- 指标卡片（净收益、最大回撤、交易次数、未成交次数）+ 净值曲线 SVG 图（复用 Token Trend Chart 的自绘折线范式）。
- 后端回测报告新增 `equity_curve`（日期×净值序列，见 B1）驱动曲线。
- 交易明细列表（入场日、入场价、信号日）替代裸数字。

**F4 策略生命周期 UI（重构 `DeskStrategiesView.vue`）**
- 列表行内操作：编辑（回填构建器）、删除、送回测（跳转回测页并预载该策略 DSL）。
- 保留"探索性策略不参与排名"的产品口径，页面上明示。

**F5 提案执行路径（`DeskProposalView.vue` + PortfolioView）**
- 提案页新增"按提案下单到模拟盘"按钮 → 确认弹窗（逐条列出 symbol/权重/股数）→ 调用 B4 接口 → 跳转模拟盘。

**F6 证据与体验补齐**
- `news-<id>` → `/news/:id` 可点击链接（`DeskStockView.vue`）。
- 机会卡增加展开态（factor_breakdown 结构化展示而非机器码）。
- 运行中心 stage 时间线中文化 + 状态徽章样式化。

### 3.2 后端功能闭环

**B1 回测真实化（`QuantDeskService.run_backtest` 重写）**
- 输入：symbol（单票）或策略作用域 + 日期区间；从 `market_data.db` 读真实 `daily_bar`。
- `features_by_date` 由真实数据计算：`main_inflow_1d`（`fund_flow_daily`）、`adv`（20 日均成交额，滚动计算）等（见 B7 因子扩展）。
- 报告新增：`equity_curve: [{date, equity}]`、`trades: [{signal_date, entry_date, entry_price, exit_date, exit_price, pnl}]`、`bars_used`。
- 覆盖率不足（bar 数 < 门槛）时显式报错提示先回填，不降级为合成数据。
- 治理不变：walk-forward 结果仍 `exploratory=true, qualified=false`。

**B2 模拟盘真实撮合**
- `place_paper_order` 改为读取该 symbol 在 `market_data.db` 的最新 `daily_bar`（收盘价撮合，涨跌停判断用当日 bar 的 open/high/low 相对前收）；无行情时拒单并提示原因（不再用合成 Bar）。
- 盘中可用自选股行情 producer 的实时快照作为第一优先价格源，`daily_bar` 兜底。

**B3 策略生命周期接口**
- 新增 `PATCH /api/quant/strategies/{id}`（编辑名称/DSL）、`DELETE /api/quant/strategies/{id}`、激活开关走现有字段。
- 策略仍不参与选票排名（exploratory 治理），激活仅代表"进入观察"。

**B4 提案→模拟盘**
- 新增 `POST /api/quant/portfolio-proposals/latest/execute`：按提案权重换算股数（A 股 100 股整数倍），逐条创建 paper order（复用 B2 撮合），返回逐条成交/拒单结果。前端确认弹窗二次确认。

**B5 每日自动化 worker（新 `backend/app/workers/quant_scheduler_worker.py`）**
- 范式复用 `base_worker.py` + `news_scheduler.py` 的调度形态。
- 交易日（`trade_calendar` 判断）盘后固定时刻（默认 16:30 本地时间，可环境变量 `QUANT_SCHEDULER_RUN_AT` 配置）执行：
  1. 增量回填：已覆盖 symbol 的当日 `daily_bar` + `fund_flow_daily`（复用东财解析器，沿用退避重试）。
  2. 运行选票流水线（`scenario=real`）。
  3. 发布事件 + 站内通知（复用现有通知通道）。
- `QUANT_SCHEDULER_ENABLED=true` 时随后端 lifespan 启停（单进程模式默认开启，与现有 producer 一致）。
- 运行状态接入 `/api/stream/status` 与运行中心（ Runs 列表 trigger 显示 `scheduled`）。

**B6 成绩单真实窗口**
- `get_report_card` 改为聚合窗口期内所有 run（7d/30d/90d 按 run 时间过滤），窗口切换产生真实差异。

**B7 财务数据与基本面 sleeve**
- 新增东财财务报表采集器（`backend/app/services/quant/market_data/eastmoney_financials.py`）：
  - 抓取季度指标：营收、归母净利润、ROE、毛利率等基础项；按报告期存储。
  - 新表落 `market_data.db`（如 `financial_fact`：symbol / period_end / metric_key / value / available_at），遵守 PIT（`available_at` = 披露日，不用未来数据）。
  - 回填 CLI 与 B5 增量任务都覆盖；单测用 fixture，不打真网（沿用现有约定）。
- 基本面打分（`factors.py::score_fundamental` 实装）：基于可得的财务因子（如净利同比、营收同比、ROE 分位）给分，数据缺失时维持显式 gap 不编造。
- 因子注册表同步扩展（`FACTOR_REGISTRY` 增加财务因子），研究包/成绩单的 fundamental 缺口随覆盖填充。

### 3.3 数据规模与限流（横切约束）
- 东财对连续抓取限流（2026-08-18 实测约 29 只后被掐）：增量任务天然是小批量（仅当日更新），风险集中在首次全量回填。
- 全量回填仍走 CLI 长跑（断点续传已有），本轮不做全量回填 UI；运行中心新增"数据健康"增强：显示最新交易日覆盖缺口与最近回填错误。

## 4. 分期交付计划

| 期 | 内容 | 产品可见增量 |
|----|------|--------------|
| A | F1～F3、F6 + B1 | 前端不再有裸 JSON；回测出真实图形化报告 |
| B | F4、F5 + B2、B3、B4、B6 | 策略可管理、提案可执行、模拟盘真实价格、成绩单窗口真实 |
| C | B5 + 运行中心增强 | 每个交易日自动出结果，无需任何手动操作 |
| D | B7 | 基本面 sleeve 出现真实候选（覆盖足够时），研究包缺口填充 |

每期独立提交、独立更新变更记录；A/B 可并行开发（前后端契约先冻结）。

## 5. 接口变化汇总

新增：
- `PATCH /api/quant/strategies/{id}`、`DELETE /api/quant/strategies/{id}`
- `POST /api/quant/portfolio-proposals/latest/execute`
- 回测报告 schema 扩展：`equity_curve` / `trades` / `bars_used`（向后兼容，新增字段）
- 财务数据相关内部表（market_data.db 新表，不动主库）

变更：
- `POST /api/quant/backtests` 请求体增加 `symbol` 与日期区间（原 DSL 逻辑不变）
- 模拟盘撮合价从合成价改为真实价（行为变化，属修复）

无旧接口删除。

## 6. 测试与验收

- 后端 TDD：回测真实化（真实库 fixture 的 walk-forward）、模拟盘真实撮合（含无行情拒单）、策略生命周期、提案执行、调度 worker 触发逻辑（时间与交易日历）、财务解析 fixture、基本面打分。
- 前端：翻译层单测、构建器双向绑定单测、回测报告组件快照/渲染测试；`npm --prefix frontend run build` 与 `check:api-drift`。
- 端到端验收（活服务实测）：回填若干真实标的 → 回测出真实曲线 → 策略保存/编辑/送回测 → 提案一键下单模拟盘真实价成交 → 手动触发一次调度任务验证自动化链路。

## 7. 风险

- 东财财务接口字段/反爬变化风险：解析器全部 fixture 化测试，失败时显式 gap 不阻塞其他 sleeve。
- 调度 worker 与手动重跑并发：复用 run 状态机的幂等约束（同 result_hash 不重复落库）。
- 全量回填耗时与限流：不在 UI 承诺全量，CLI 长跑为主。
- 净值曲线在长区间（3 年日线）下的渲染量：SVG 折线做抽样降采样。
- 财务数据 PIT 误差（披露日精确到日）：`available_at` 采用披露日 T 日，回测特征只用已披露期数据。
