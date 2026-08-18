# 当前系统快照（2026-08-18）

本文档是后续优化和开发的**现状入口**。它描述仓库在 2026-08-18 时已经具备的能力，而不是早期规划里“打算做但还没做”的事项。

不要把 `docs/archive/`、根目录历史 `plan.md` 归档稿、或已完成的设计/计划当作当前待办。新工作应从代码、OpenAPI 和本快照出发，而不是复述旧优化清单。

## 产品定位

本地单用户的消息工作台，正在升级为量化交易与个股情报台：默认首页是机会雷达 `/desk`，新闻流仍是支撑视图。系统不承诺收益；没有过线机会时现金是合法结果。交易台骨架与独立行情库已上线；机会流水线仍用合成夹具，未接入真实因子/LLM。

- 使用形态：本机运行，浏览器访问
- 存储：主库 SQLite `app.db`；独立行情库 `backend/data/market_data.db`（东财日线/资金流，需 `make quant-backfill`；未回填时覆盖率为 0）
- 实时性：准实时（秒到分钟级），不承诺交易所级行情
- 市场：选股/资金流/回测以 A 股为主；美/港股维持现有行情展示

## 已经具备的能力

| 模块 | 入口 / 关键能力 |
|------|-----------------|
| 交易台 | `/desk`（默认首页），机会雷达骨架：状态带、空态机会流、手动重跑合成流水线；`/desk/ops` 运行中心数据健康 Tab |
| 新闻流 | `/news`，多源抓取、去重、主题聚合、事件详情、手动刷新；pipeline 阶段 2 会写入 A 股 rule mention |
| 仪表盘 | `/dashboard`，市场总览、情绪/恐慌可视化、动态行情条 |
| 自选股 | `/watchlist`，全量 A 股检索、真实行情、K 线、关联新闻；A 股详情含资金流面板（无数据时合法空态） |
| 持仓 | `/portfolio` |
| AI 对话 | `/chat`，多模型、流式回答、可选推理面板、新闻上下文追问 |
| LLM 设置 | `/settings/llm`，多模型配置弹窗、Token 用量账本 |
| 通知 | `/settings/notify`，站内通知与飞书等通道 |
| X Monitor | `/x-monitor`，可选 Twitter/X 增强层，不并入新闻主链路 |
| 日历 | `/calendar`，财报等事件 |
| 日报 | `/digest` |
| 主题 | `/topics/:id` |
| 运维 | `/ops`，运行状态与源健康 |
| 情绪评测 | `/eval/sentiment` |
| 信号统计 | `/analytics/backtest`，新闻情绪信号命中率（不是策略回测引擎） |

后端还包括：新闻调度 worker、正文/评分 pipeline、行情 producer、市场总览 producer、结构化日志与请求链路、Redis 混合事件层（不可用时降级进程内总线）、SSE 推送。

## 权威来源（按优先级）

1. **代码**：`backend/`、`frontend/`、Alembic 迁移
2. **接口**：`frontend/openapi.json` 与后端实际路由，而不是早期 API 契约草稿
3. **运行方式**：根目录 [README.md](../README.md)
4. **近期冲突检查**：只读 [code-change-log.md](./code-change-log.md) 顶部近期条目
5. **原则**：[stability-and-evolution.md](./stability-and-evolution.md) 中的稳定性原则仍然有效；具体实现以代码为准

## 明确不是当前待办的材料

以下内容只读，**不要据此重新实施或“补齐未完成阶段”**：

- `docs/archive/superpowers/`：已落地或已过期的设计/计划
- `docs/archive/optimization-2026-06/`：2026-06 十三项优化，已全部落地
- `docs/archive/bootstrap/`：项目启动期总控计划、初期项目管理、并行开发提示词、旧优化诊断清单
- `docs/archive/code-change-log-before-2026-08.md`：2026-07 及更早的变更流水
- `docs/product-requirements.md`、`docs/technical-architecture.md`、`docs/api-contract.md`：第一阶段草稿，字段和模块名可能落后于代码

## 后续开发约定

- 新功能先在 `docs/superpowers/` 写设计与计划；完成后立刻归档。
- 若用户要求优化，先对照当前代码定位问题，不要从旧清单里挑剩余项继续做。
- 旧文档里的“未做 / 部分完成 / 风险或后续事项”不自动继承为新任务。
