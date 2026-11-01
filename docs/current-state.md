# 当前系统快照（2026-11-01，聚焦改造 P2 之后）

本文档是后续优化和开发的**现状入口**。它描述仓库当前已经具备的能力，而不是规划中"打算做但还没做"的事项。

不要把 `docs/archive/`、根目录历史 `plan.md` 归档稿、或已完成的设计/计划当作当前待办。新工作应从代码、OpenAPI 和本快照出发。

## 产品定位

本地单用户的 **A 股盯盘与复盘台**（改造进行中）：信息源要宽（美股、亚太、A 股新闻与指数），输出要窄（只给结论）。盘中由系统替用户盯盘，盘后集中复盘。

- 改造设计：[superpowers/specs/2026-10-31-focus-redesign-design.md](./superpowers/specs/2026-10-31-focus-redesign-design.md)（P1～P4 分期；P1、P2 已完成）
- 使用形态：本机运行，浏览器访问
- 存储：单一 SQLite 主库 `backend/data/app.db`（原独立行情库 `market_data.db` 已下线，最终数据备份在 `backend/data/backups/market_data-final-20261101.db`）
- 实时性：准实时（秒到分钟级），不承诺交易所级行情
- 市场：主做 A 股；美股、港股、日韩、欧股作为传导与参考

## 已经具备的能力

| 模块 | 入口 / 关键能力 |
|------|-----------------|
| 首页 | `/` 临时重定向到 `/dashboard`（P4 将替换为"盯盘台"仪表盘） |
| 仪表盘 | `/dashboard`，市场总览（美股、A 股、日经、KOSPI、欧股指数与 ETF）、情绪与恐慌指标、动态行情条 |
| 新闻流 | `/news`，34 个源多源抓取、去重、正文爬取、主题聚合、事件详情、手动刷新；新闻落库后由 `a_share_mentions` 按 A 股名称/代码写入 `news_stock_mention`（新闻↔个股关联） |
| 主题 / 事件 | `/topics/:id`、`/news/events/:eventKey`、`/news/sentiment/:sentiment` |
| 自选股 | `/watchlist`、`/watchlist/:symbol`：全量 A 股检索、真实行情、K 线、关联新闻、情绪时间线；"行情"标签内填写持仓数量与成本，有持仓的股票以警示色条和"持仓"标签高亮；"组合"标签展示市值、盈亏与按仓位加权的新闻；A 股详情含资金流面板（`GET /api/market/symbols/{symbol}/fund-flow`，东财按需拉取 + 10 分钟缓存，约 60 个交易日） |
| 每日复盘 | `/digest`，盘前/盘后简报（P4 将升级为 AI 盘后简报 + 明日关注 + 早间隔夜简报） |
| 日历 | `/calendar`，财报等事件（P4 将并入首页与简报后删除页面） |
| LLM 设置 | `/settings/llm`，多模型配置、连接测试、Token 用量账本（单价为美元/百万 token）、AI 漏斗状态卡（是否在线、今日处理量与费用） |
| AI 漏斗 | `AiFunnelWorker`：自选股板块推断 → L1 粗筛（标题+摘要，批量）→ L2 精读（全文，每天 ≤300 条）→ 提醒；只用明确设为默认的模型。新闻详情"AI 影响"卡可修正（`PUT /api/news/{id}/impacts`），修正作为后续示例；个股详情有 AI 影响列表；自选页"关注板块"可增删（`/api/focus-sectors`）。代码在 `app/services/ai/` |
| 提醒中心 | `/alerts` + 侧栏未读角标 + 页面内弹窗（SSE `alert.created`）：持仓全天涨跌 ±5%（交易时段内、当天行情在动、每股每天一次）、持仓股新闻立即提醒，仅关注股新闻每 30 分钟合并；北京时间 22:00～08:00 静默，早上归入"隔夜汇总"。AI 在线时持仓新闻由 AI 判断（利多/利空且强度 ≥ 中），另有海外重大、关注板块、新机会提醒；AI 不在线或 15 分钟内没结论时回退标题关键词规则。规则在 `app/services/alert_service.py` |
| 系统健康 | `/ops`，worker、新闻源、LLM 用量、事件层、数据库体积与告警 |

后端还包括：新闻调度 worker、正文/评分 pipeline、行情 producer、市场总览 producer、结构化日志与请求链路、Redis 混合事件层（不可用时降级进程内总线）、SSE 推送、每日备份与数据清理。

## P1 已下线（2026-11-01）

量化交易台（`/desk*`、选票流水线、策略 DSL、回测实验室、成绩单、组合提案、模拟盘、盘后量化调度、`market_data.db`）、AI 对话（`/chat`、`POST /api/llm/chat`）、X 监控（`/x-monitor`、`/api/x/*`、`/api/health/x`）、信号统计（`/analytics/backtest`）、情绪评测与相关性实验工具（`/eval/sentiment`、标注/实验脚本）、情绪置信度校准（从未启用）。对应数据表已通过可回退的 Alembic 迁移删除，删除前的主库完整备份在 `backend/data/backups/app-before-focus-p1-20261101.db`。代码可从 git 历史找回。

## P2 已完成（2026-11-01）

站内提醒（`alert` 表、`/api/alerts*`、`AlertService`）取代飞书推送；删除 `/settings/notify`、`feishu_notify_config` / `notification_job` 表、独立的 `/portfolio` 页面、自选股单股阈值（`alert_threshold` / `alert_mode` 列）。备份：`backend/data/backups/app-before-focus-p2-20261101.db`。

## P3 代码已完成（2026-11-01），待真实运行验收

AI 漏斗（`news_ai_screen` / `news_ai_analysis` / `news_impact` / `impact_correction` / `stock_sector` / `focus_sector_override` / `ai_alert_deferral` 表，`/api/news/{id}/ai`、`/api/news/{id}/impacts`、`/api/watchlist/{symbol}/impacts`、`/api/focus-sectors`、`/api/ai/funnel/status`）。LLM 单价改为每百万 token。事件聚类收紧：无关键词新闻不再落进兜底事件，通用词不再把无关新闻串成巨型事件。备份：`backend/data/backups/app-before-focus-p3-20261101.db`、`app-before-topic-prune-20261101.db`。验收还差：用户在模型设置配好 terra 后跑一个真实交易日的 token 统计。板块行情异动提醒未做（放到 P4）。

## 后续分期（见设计文档 §7）

- **P4 盯盘台与简报**：首页仪表盘、盘后简报 + 明日关注、早间隔夜简报；日历与复盘页并入后删除。

## 权威来源（按优先级）

1. **代码**：`backend/`、`frontend/`、Alembic 迁移
2. **接口**：`frontend/openapi.json` 与后端实际路由，而不是早期 API 契约草稿
3. **运行方式**：根目录 [README.md](../README.md)
4. **近期冲突检查**：只读 [code-change-log.md](./code-change-log.md) 顶部近期条目
5. **原则**：[stability-and-evolution.md](./stability-and-evolution.md) 中的稳定性原则仍然有效；具体实现以代码为准

## 明确不是当前待办的材料

以下内容只读，**不要据此重新实施或"补齐未完成阶段"**：

- `docs/archive/superpowers/`：已落地或已过期的设计/计划（含已下线的量化交易台 Phase 0～5）
- `docs/archive/optimization-2026-06/`：2026-06 十三项优化，已全部落地
- `docs/archive/bootstrap/`：项目启动期总控计划、初期项目管理、并行开发提示词、旧优化诊断清单
- `docs/archive/code-change-log-before-2026-08.md`：2026-07 及更早的变更流水
- `docs/product-requirements.md`、`docs/technical-architecture.md`、`docs/api-contract.md`：第一阶段草稿，字段和模块名可能落后于代码

## 后续开发约定

- 新功能先在 `docs/superpowers/` 写设计与计划；完成后立刻归档。
- 若用户要求优化，先对照当前代码定位问题，不要从旧清单里挑剩余项继续做。
- 旧文档里的"未做 / 部分完成 / 风险或后续事项"不自动继承为新任务。
