# 量化交易台 Phase 0 实施计划

- 日期：2026-08-18
- 状态：已完成
- 对应设计：[docs/superpowers/specs/2026-08-18-quant-trading-desk-design.md](../../../superpowers/specs/2026-08-18-quant-trading-desk-design.md) §16 Phase 0
- 前置：`docs/current-state.md`、根目录 `README.md`

## 目标

用合成数据钉死决策契约与防前视规则，让 API 与 `/desk` 能表达「无合格机会」。不接入真实行情库、采集器、LLM 或回测引擎。

## 范围

**做：**

- `services/quant/` 纯函数内核：PIT 截点、财务修订、除权、板块涨跌停/T+1、U0/U2、候选状态机、三 sleeve 合成案例、run hash
- 主库表：`recommendation_run`、`recommendation_item`、`quant_run_stage_log`
- API：`GET/POST /quant/recommendations/*`、`GET /quant/data/status`、`GET /quant/radar`
- `/desk` 骨架页设为默认首页；导航新增「交易台」；空态一等公民
- `requirements.txt` 显式锁定 `pandas`/`numpy`，新增锁定 `pyarrow`

**不做：** `market_data.db`、东财采集、mention 补齐、真实因子/LLM、DSL、向量化回测、模拟盘、运行中心完整页、SSE 新事件。不改 `/api/backtest` 与 `/portfolio`。

## TDD 任务

1. 失败测试：`backend/tests/quant/test_pit.py`、`test_fills.py`、`test_universe.py`、`test_candidate.py`、`test_pipeline_repro.py`
2. 实现 `backend/app/services/quant/` 使上述测试变绿
3. 模型 + Alembic（`down_revision=e6c2a9f4d1b7`，幂等 create_table）+ 路由
4. `backend/tests/test_quant_api.py`：无 run 空态、abstain 空列表、mixed 三 sleeve、幂等重跑、hash 落库
5. 前端 Desk 页、导航、store、OpenAPI 类型生成；同步 router/AppShell/smoke 测试

## 验收

- 晚间公告、财务更正、除权、三板块涨跌停、停牌、T+1 用例全绿
- 同版本两次 run hash 一致
- API 与 `/desk` 能展示「今日无正期望机会」及未过线原因
- `pytest backend/tests/quant backend/tests/test_quant_api.py`、相关前端测试、`npm --prefix frontend run build`、`check:api-drift`

## 后续

Phase 0 合入后另写 `2026-08-18-quant-desk-phase1-plan.md`：独立 `market_data.db`、日线/资金流采集、运行中心「数据健康」Tab。
