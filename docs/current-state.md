# 当前系统快照（2026-08-18）

本文档是后续优化和开发的**现状入口**。它描述仓库在 2026-08-18 时已经具备的能力，而不是早期规划里“打算做但还没做”的事项。

不要把 `docs/archive/`、根目录历史 `plan.md` 归档稿、或已完成的设计/计划当作当前待办。新工作应从代码、OpenAPI 和本快照出发，而不是复述旧优化清单。

## 产品定位

本地单用户的消息工作台，已升级为量化交易与个股情报台：默认首页是机会雷达 `/desk`，新闻流仍是支撑视图。系统不承诺收益；没有过线机会时现金是合法结果。LLM 不改排名或仓位。

- 使用形态：本机运行，浏览器访问
- 存储：主库 SQLite `app.db`；独立行情库 `backend/data/market_data.db`（东财日线/资金流，需 `make quant-backfill`；未回填时覆盖率为 0）
- 实时性：准实时（秒到分钟级），不承诺交易所级行情
- 市场：选股/资金流/回测以 A 股为主；美/港股维持现有行情展示

## 已经具备的能力

| 模块 | 入口 / 关键能力 |
|------|-----------------|
| 交易台首页 | `/desk`：状态带、图形化仪表盘（覆盖率/漏斗/最近运行/提案权重）、机会卡/空态、事件雷达列；手动重跑默认走真实行情流水线（`scenario=real`），合成夹具保留用于测试 |
| 个股研究 | `/desk/stocks/:symbol`：K 线（日/周，复用 KlineChart）、A 股资金流面板、纵横研究包、显式缺口、「问 AI」装载研究上下文；K 线接口不再要求标的在自选股内 |
| 组合提案 | `/desk/portfolio-proposal`：现金底仓与分配器权重，LLM 不参与；支持「按提案下单到模拟盘」（100 股整数倍换算，无行情/不足 1 手自动拒单，同 run 防重复执行） |
| 成绩单 | `/desk/report-card`：按 sleeve 漏斗计数；7d/30d/90d 窗口真实聚合窗口内全部 run；财务未覆盖前不宣称超额收益 |
| 策略工作台 | `/desk/strategies`：因子注册表表格（含财务因子）、DSL 结构化条件构建器（因子/运算符/阈值行 + 高级 JSON 模式）、策略编辑/删除/一键送回测；空库启动种子 3 条探索性默认策略（每 sleeve 一条，`is_active=0`） |
| 回测实验室 | `/desk/backtest`：walk-forward 接真实 `market_data.db` 日线/资金流（bar 数不足显式报错不降级合成），报告含净值曲线/指标卡片/交易明细；探索性且不得 qualified |
| 运行中心 | `/desk/ops`：流水线 Runs（trigger 区分手动/每日自动）、数据健康（含最近自动运行日）、AI 审计、决策日志 |
| 每日自动化 | 交易日盘后（默认 16:30）`quant_scheduler` worker 自动增量回填 + 跑真实选票流水线 + 发布事件；`QUANT_SCHEDULER_RUN_AT` 可配；手动兜底 `POST /api/quant/scheduler/run` |
| 基本面数据 | 东财主要财务指标（`financial_fact` 表，PIT 披露日）；基本面 sleeve 用真实单季同比/ROE 打分，只产 WATCH 暂不晋级；研究包 valuation 用真实财务填充 |
| 模拟盘 | `/portfolio` 增加确认后撮合的 paper account；停牌/未确认不成交 |
| 新闻流 | `/news`，多源抓取、去重、主题聚合、事件详情、手动刷新；pipeline 阶段 2 写入 A 股 rule mention 并进入快循环雷达 |
| 仪表盘 | `/dashboard`，市场总览、情绪/恐慌可视化、动态行情条 |
| 自选股 | `/watchlist`，全量 A 股检索、真实行情、K 线、关联新闻；A 股详情含资金流面板 |
| AI 对话 | `/chat`，多模型、流式回答；`desk_symbol` 研究副驾只读，不改排名/仓位 |
| LLM 设置 | `/settings/llm`，多模型配置弹窗、Token 用量账本 |
| 通知 | `/settings/notify`，站内通知与飞书等通道 |
| X Monitor | `/x-monitor`，可选 Twitter/X 增强层，不并入新闻主链路 |
| 日历 | `/calendar`，财报等事件 |
| 日报 | `/digest` |
| 主题 | `/topics/:id` |
| 运维 | `/ops`，运行状态与源健康 |
| 情绪评测 | `/eval/sentiment` |
| 信号统计 | `/analytics/backtest`，新闻情绪信号命中率（不是策略回测引擎） |

选票流水线：`POST /api/quant/recommendations/run` 默认 `scenario=real`，基于 `market_data.db` 真实日线/资金流跑三 sleeve 规则打分（trend 可 qualify；event 由新闻 rule mention 驱动、grade C 只进 WATCH；fundamental 由东财财务单季同比/ROE 打分、只产 WATCH 暂不晋级），涨跌停开盘不可成交降级，组合提案由 allocator 从 qualified 派生（vol 用 20 日日收益标准差）。行情覆盖率以 `GET /api/quant/data/status` 真实计数为准；`make quant-backfill` 支持 `QUANT_BACKFILL_LIMIT/SLEEP/DAYS/FINANCIALS` 环境变量与失败退避重试；每日盘后由 `quant_scheduler` worker 自动增量回填 + 跑流水线（`QUANT_SCHEDULER_RUN_AT` 默认 16:30，`QUANT_SCHEDULER_ENABLED` 默认 true 随后端启停）。

后端还包括：新闻调度 worker、正文/评分 pipeline、行情 producer、市场总览 producer、结构化日志与请求链路、Redis 混合事件层（不可用时降级进程内总线）、SSE 推送。量化内核含 PIT/除权/涨跌停/T+1、三 sleeve 规则打分、组合分配器、DSL、真实数据 walk-forward 回测、模拟盘真实价撮合与每日盘后调度。

## 权威来源（按优先级）

1. **代码**：`backend/`、`frontend/`、Alembic 迁移
2. **接口**：`frontend/openapi.json` 与后端实际路由，而不是早期 API 契约草稿
3. **运行方式**：根目录 [README.md](../README.md)
4. **近期冲突检查**：只读 [code-change-log.md](./code-change-log.md) 顶部近期条目
5. **原则**：[stability-and-evolution.md](./stability-and-evolution.md) 中的稳定性原则仍然有效；具体实现以代码为准

## 明确不是当前待办的材料

以下内容只读，**不要据此重新实施或“补齐未完成阶段”**：

- `docs/archive/superpowers/`：已落地或已过期的设计/计划（含量化交易台 Phase 0～5）
- `docs/archive/optimization-2026-06/`：2026-06 十三项优化，已全部落地
- `docs/archive/bootstrap/`：项目启动期总控计划、初期项目管理、并行开发提示词、旧优化诊断清单
- `docs/archive/code-change-log-before-2026-08.md`：2026-07 及更早的变更流水
- `docs/product-requirements.md`、`docs/technical-architecture.md`、`docs/api-contract.md`：第一阶段草稿，字段和模块名可能落后于代码

## 后续开发约定

- 新功能先在 `docs/superpowers/` 写设计与计划；完成后立刻归档。
- 若用户要求优化，先对照当前代码定位问题，不要从旧清单里挑剩余项继续做。
- 旧文档里的“未做 / 部分完成 / 风险或后续事项”不自动继承为新任务。
