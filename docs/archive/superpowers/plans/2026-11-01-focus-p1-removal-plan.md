# 聚焦改造 P1：删除与合并 实施计划（2026-11-01）

> 设计：[2026-10-31-focus-redesign-design.md](../../../superpowers/specs/2026-10-31-focus-redesign-design.md)
> 状态：**已完成（2026-11-01）并归档**。执行记录见 `docs/code-change-log.md` 中 P1-T1～T8 条目。
> 分支：`refactor/focus-p1`（从 `main` 切出），每个任务一个提交，每个提交同步更新 `docs/code-change-log.md`。

## 0. 范围

**P1 做**：删除量化台（含模拟盘、`market_data.db` 基础设施）、AI 对话、X 监控、信号统计、情绪评测工具；把 A 股资金流从量化模块迁出为轻量按需服务；导航收敛。

**P1 不做（移到后续期，避免出现"删了但替代品还没有"的空窗）**：

| 事项 | 移到 | 原因 |
|---|---|---|
| 删除飞书推送、`/settings/notify` | P2 | 与站内提醒中心一起替换；`notification_job` 已有 `channel` 字段，P2 直接换通道 |
| 自选股与组合合并为"持仓与关注" | P2 | 与真实持仓字段一起做 |
| 删除日历页、每日复盘页 | P4 | 其内容要先并入首页仪表盘 |
| 首页仪表盘 | P4 | P1 期间 `/` 临时重定向到 `/dashboard` |

**删除时的保留例外**（引用分析确认被主链路使用）：

- `sentiment_calibration.py`：被 `news_signal_classifier.py` 引用；它本身不导入 `signal_backtest.py`（模块内注释已声明），可直接保留。
- `news_relevance_evaluator.py`：被 `news_priority.py` 引用。
- `test_kline_non_watchlist.py`：测的是行情 K 线接口对非自选标的的支持，与量化无代码依赖，保留（只改注释）。
- `news_stock_mention` 的主写入方 `news_signal_pipeline.py` 不依赖量化模块。

## T0 基线与备份

1. `git switch -c refactor/focus-p1`。
2. 备份：`backend/data/app.db` → `backend/data/backups/app-before-focus-p1-<日期>.db`；`backend/data/market_data.db` → `backend/data/backups/market_data-final-<日期>.db`（删除基础设施后不再使用，但保留数据文件）。
3. 记录基线：
   - `conda run -n news-caught pytest backend/tests -q`（已知基线：1341 passed / 7 failed，来自审计文档）
   - `conda run -n news-caught ruff check backend`（已知 4 个错误，均在将删除的 quant 测试里）
   - `npm --prefix frontend run test`、`npm --prefix frontend run build`
4. 基线结果写入本计划 §附录，作为"删除后不得新增失败"的比对依据。

## T1 资金流迁出（TDD）

先迁移，再删量化，保证个股详情的资金流面板全程可用。

1. **测试先行**：新建 `backend/tests/test_fund_flow_service.py`
   - 复用 `tests/quant/test_eastmoney_parsers.py` 中资金流解析的夹具（不打真网）。
   - 用例：A 股代码解析正确；非 A 股返回空 + note；上游失败返回空 + note、不抛 500；TTL 内第二次调用不再请求上游。
   - 路由用例：`GET /api/market/symbols/{symbol}/fund-flow` 返回字段与旧 `QuantFundFlowView` 一致（`symbol`、`points[trade_date, main_net_inflow, super_large_net, large_net, medium_net, small_net, main_net_pct]`、`note`）。
2. **实现**：
   - 新建 `backend/app/services/fund_flow_service.py`：从 `quant/market_data/eastmoney_fund_flow.py` 迁入 `parse_fund_flow_payload` / `fetch_fund_flow`，按需拉取最近 60 个交易日，进程内 TTL 缓存（默认 600 秒，`FUND_FLOW_CACHE_TTL_SECONDS` 可配）。
   - `backend/app/schemas/market.py` 新增 `FundFlowView` / `FundFlowPointView`。
   - `backend/app/api/routes/market.py` 新增路由。
3. **前端**：`FundFlowPanel.vue` 与 `WatchlistDetailView.vue` 改调新地址；更新 `client.ts`、`types/api.ts`、对应单测。
4. 重新生成 `frontend/openapi.json` 与 `types/generated/api.d.ts`，通过 `check:api-drift`。
5. 验证：新测试通过；`make dev` 打开一只 A 股（如 002384.SZ）详情页，资金流面板有数据。

## T2 删除量化台（后端）

1. 删除：`app/api/routes/quant.py`、`app/services/quant/`（整目录）、`app/services/quant_desk_service.py`、`app/workers/quant_scheduler_worker.py`、`app/schemas/quant.py`、`app/models/quant.py`、`app/models/market_data.py`、`app/db/market_initializer.py`、`app/db/market_session.py`、`backend/alembic_market/`、根目录 `alembic_market.ini`。
2. 修改：
   - `app/api/router.py`：移除 `quant`。
   - `app/main.py`：移除 `quant_scheduler_worker` 的启动与停止。
   - `app/db/initializer.py`：移除 `initialize_market_database()` 调用与量化模型注册。
   - `app/models/__init__.py`：移除量化模型导出。
   - `app/core/config.py`：移除 `quant_*`、`market_database_url`。
   - `Makefile`：移除 `quant-backfill` 目标与 `.PHONY` 项。
   - `.env.example`：移除 `QUANT_*`。
3. 主库迁移：新增 Alembic 迁移，删除 `models/quant.py` 中的 15 张表：`recommendation_run`、`recommendation_item`、`radar_event`、`research_snapshot`、`llm_role_binding`、`ai_call_audit`、`portfolio_proposal`、`portfolio_proposal_item`、`quant_strategy`、`quant_backtest_run`、`paper_account`、`paper_order`、`paper_trade`、`decision_log`、`quant_run_stage_log`。`downgrade` 重建表结构。
   - `llm_role_binding` 只被量化模块使用；设计已改为单模型，一并删除。
4. 删除测试：`tests/quant/`、`tests/test_quant_api.py`；修 `test_migration_parity.py` 使其通过。
5. 验证：`pytest backend/tests` 无新增失败；`ruff check backend` 无错误；`alembic upgrade head` 在备份副本上执行成功、`alembic downgrade -1` 可回退；后端启动无报错。

## T3 删除量化台（前端）

1. 删除：`views/Desk*.vue` 与对应测试（7 个页面）、`components/quant/`、`stores/deskStore.{ts,test.ts}`、`constants/quantLabels.{ts,test.ts}`、`api/mock/quant.ts`。
2. 修改：
   - `router/index.ts`：移除 7 条 `/desk*` 路由；`/` 重定向到 `/dashboard`。
   - `AppShell.vue`：移除"交易台"导航组与 `/desk` 激活逻辑。
   - `PortfolioView.vue`：移除模拟盘区块（`paper*` 状态、`getQuantPaperAccount` 等）。
   - `api/client.ts`、`api/mock.ts`、`types/api.ts`：移除 quant 相关函数与类型。
   - `smoke/app-navigation.test.ts`：更新导航断言。
3. 验证：`npm --prefix frontend run test`、`npm --prefix frontend run build`、`check:api-drift` 通过。

## T4 删除 AI 对话

1. 后端：`app/api/routes/llm.py` 删除 `POST /chat` 及仅为其服务的辅助函数（含 `desk_symbol` 分支与对量化的导入）；保留 `config*`、`translate`、`test`、`stats`、`ping`。对应 schema 中聊天请求类型一并删除。删除 `tests/test_llm_chat.py`。
2. 前端：删除 `views/ChatView.{vue,test.ts}`、`components/chat/`、`composables/useChatStream.ts`（及测试）；从路由、`AppShell.vue`（导航项与 `isChatRoute` 布局分支）、`client.ts`、类型中移除。
3. 验证：后端 LLM 相关测试通过；前端 test 与 build 通过；`/settings/llm` 的连接测试仍可用。

## T5 删除 X 监控

1. 后端删除：`app/services/x_monitor/`、`x_radar_signal_builder.py`、`twitterapi_io_client.py`、`app/workers/x_health_probe_worker.py`、`app/api/routes/x_monitor.py`、`repositories/x_*`、`models/x_*`（6 个模型）、相关 schema、`tests/test_x_monitor.py`、`tests/test_x_health_probe_worker.py`。
2. 修改：`router.py`、`main.py`（探针启停）、`workers/pipeline_worker_main.py`（探针）、`db/initializer.py`、`models/__init__.py`、`core/config.py`（`X_MONITOR_*`、`TWITTERAPI_IO_*`）、`.env.example`、`api/routes/health.py` 与 `schemas/health.py`。
3. 主库迁移：删除 6 张 `x_*` 表：`x_account`、`x_post`、`x_post_symbol_mention`、`x_signal`、`x_signal_post_link`、`x_source_health`。
4. 前端删除：`views/XMonitorView.{vue,test.ts}`、`stores/xMonitorStore.{ts,test.ts}`；`client.ts`、`api/mock/ops.ts`、类型、路由、导航中的 X 相关内容；运行状态条若展示 X 健康，一并移除。
5. 接口变化：`GET /api/health` 响应移除 `x_monitor_enabled`、`x_monitor_healthy`。前端同步修改；此接口无外部调用方。
6. 用户本地 `.env` 中残留的 `X_MONITOR_*` / `TWITTERAPI_IO_*` 键无害（设置模型若为 `extra="forbid"` 需确认，必要时提示用户删除）。
7. 验证：pytest、ruff、前端 test 与 build；`/api/health` 正常。

## T6 删除信号统计与情绪评测工具

1. 后端删除：
   - 路由：`app/api/routes/backtest.py`、`app/api/routes/eval.py`
   - 服务：`signal_backtest.py`、`news_sentiment_dataset.py`、`news_sentiment_evaluator.py`、`news_sentiment_experiment_runner.py`、`news_sentiment_llm_classifier.py`、`news_sentiment_report.py`、`news_relevance_dataset.py`、`news_relevance_annotation.py`、`news_relevance_report.py`、`news_relevance_experiment_runner.py`、`sentiment_eval_persistence.py`
   - 数据层：`repositories/sentiment_eval_run*`、`models/sentiment_eval_run.py`
   - schema：`schemas/backtest.py`、eval 相关 schema
   - 测试：对应的 `test_signal_backtest.py`、`test_eval_sentiment_route.py`、`test_news_sentiment_*`、`test_news_relevance_{dataset,annotation,report,experiment_runner}.py`、`test_sentiment_eval_*`、`test_sentiment_dataset_tools.py`
   - 脚本：`backend/scripts/` 下仅为评测服务的脚本
2. 保留：`sentiment_calibration.py`、`news_relevance_evaluator.py`（及其测试）。删除前逐个 `grep` 确认没有保留模块导入被删模块；若 `sentiment_calibration` 使用的校准表依赖评测产物，改为读取现有落盘文件或默认值，并补测试。
3. 修改：`router.py`、`config.py`（`signal_backtest_*`、eval 相关项）、`models/__init__.py`、`db/initializer.py`。
4. 主库迁移：删除 `sentiment_eval_run` 表。
5. 前端删除：`views/SignalBacktestView.*`、`views/SentimentEvalView.*`、`api/mock/sentimentEval.ts` 及 `client.ts`、类型、路由、导航中的对应项。
6. 验证：pytest（重点 `test_news_signal_*`、`test_news_priority.py`、`test_sentiment_calibration.py`）、ruff、前端 test 与 build。

## T7 导航收敛与文档

1. `AppShell.vue` 导航收敛为三组（P2、P4 还会继续调整）：
   - **盯盘**：仪表盘、最新事件、每日复盘、日历
   - **持仓**：自选股、组合
   - **系统**：模型设置、通知、系统健康
2. 更新 `README.md`（删除量化回填、X 监控、`make quant-backfill` 等段落；修正仓库路径）、`docs/current-state.md`（能力表按 P1 后的实际情况重写）、`.env.example`。
3. 重新生成 `frontend/openapi.json` 与类型，`check:api-drift` 通过。

## T8 全量验证与评审

1. `conda run -n news-caught pytest backend/tests`：失败数 ≤ 基线（预期原有 7 个失败中与量化相关的随之消失）。
2. `conda run -n news-caught ruff check backend`：无错误（CI 第一步）。
3. `npm --prefix frontend run test`、`npm --prefix frontend run build`、`check:api-drift`。
4. 在备份副本上执行 Alembic `upgrade head` 和 `downgrade` 往返；随后对真实 `app.db` 执行 `upgrade`（启动时自动执行）。
5. `make dev` 手动走一遍所有保留页面：仪表盘、最新事件、新闻详情、事件详情、主题、情绪新闻、自选股与详情（K 线、资金流、关联新闻）、组合、每日复盘、日历、模型设置、通知、系统健康；控制台无报错，后端日志无异常。
6. 统计删除规模（文件数、行数），写入变更记录。
7. 代码评审：对整个分支做一次 review，逐项处理意见。
8. 完成后把本计划移到 `docs/archive/superpowers/plans/`；设计文档等全部分期完成后再归档。

## 风险与回退

| 风险 | 缓解 |
|---|---|
| 误删主链路依赖 | 每个任务先 `grep` 引用分析，删除后立即跑全量测试；按任务分别提交，可逐个 `git revert` |
| 数据库删表不可逆 | T0 备份；迁移带 `downgrade`；`market_data.db` 文件保留在 backups |
| 资金流上游（东财 push2）无 SLA | 失败时返回空数据和说明，不报 500；TTL 缓存减少请求 |
| 用户本地 `.env` 残留已删配置项 | 确认 settings 是否忽略未知键；必要时在变更记录中提示 |
| 未提交的审计修复文档（2026-09-28）与本次改动重叠 | P1 完成后，审计中量化相关的条目自然失效；剩余条目（FTS、市场总览 single-flight、topics 冷缓存、测试污染）在 P1 后单独处理 |

## 附录：基线记录

2026-11-01 T0 实测（分支 `refactor/focus-p1`，删除前）：

- 后端 `pytest backend/tests`：**1339 passed / 9 failed**。
  - 7 个为审计文档已知的测试种子污染：`test_news.py` 3 个、`test_news_analysis.py` 4 个。
  - 2 个为硬编码旧路径 `/Users/xiuyang/Desktop/news-caught`：`test_news_relevance_experiment_runner.py`、`test_news_relevance_report.py`（均属 T6 删除范围）。
- `ruff check backend`：4 个错误（均在 `tests/quant/` 与 `test_quant_api.py`，属 T2 删除范围）。
- 前端 `vitest run`：99 个文件、568 passed；`npm run build` 通过；`check:api-drift` OK。
- 备份：`backend/data/backups/app-before-focus-p1-20261101.db`、`backend/data/backups/market_data-final-20261101.db`（命名不匹配备份 worker 的 `app_*.db` 清理规则，不会被自动删除）。

## 完成记录（2026-11-01）

- 分支 `refactor/focus-p1`，T0～T8 共 9 个提交；相对 `main` 共 246 个文件，删除约 4 万行。
- 后端 1051 passed / 7 failed（已知测试污染，基线为 1339 / 9）；前端 79 个文件、462 passed；构建与 `check:api-drift` 通过。
- 真实 `app.db` 已升级到 `c4e1d7a9b2f8`，删表前完整备份为 `backend/data/backups/app-before-focus-p1-20261101.db`。
- 相对计划的偏离：
  1. `sentiment_calibration` 原计划保留；核查后发现其开关默认关闭、从未启用，唯一生成方是被删除的信号统计，因此一并删除（T6）。
  2. 计划外发现并处理：新闻主流程依赖量化模块里的 A 股名称匹配，迁出到 `a_share_mentions.py`（T2）；东财资金流原解析器列顺序颠倒、原地址只返回 1 天，已修正（T1）；新闻详情页残留的"问 AI"按钮（T7）；已下线 worker 的心跳残留（T8）。
