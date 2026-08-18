# 量化交易台补全实施计划(2026-08-18)

对应设计:`docs/superpowers/specs/2026-08-18-quant-desk-real-pipeline-design.md`。三路并行,文件范围互不重叠;提交用显式 `git add <files>`。

## 任务 1(backend):真实流水线 + 因子端点 + 默认策略种子

文件范围:`backend/app/services/quant/recommendation/`(新增 market_pipeline.py)、`backend/app/services/quant/contracts.py`、`backend/app/services/quant_desk_service.py`、`backend/app/api/routes/quant.py`、`backend/app/schemas/quant.py`、`backend/app/main.py`(或现有 seed 入口)、`backend/tests/quant/test_market_pipeline.py`(新)、`backend/tests/test_quant_api.py`、`frontend/openapi.json`(重新导出)。

验收:
- `NEWS_CAUGHT_TEST_DB=... conda run -n news-caught pytest backend/tests/quant backend/tests/test_quant_api.py` 全绿;单测不打真网,市场库用临时 SQLite 夹具。
- `POST /run {"scenario":"real"}` 在有行情数据时产出候选(trend sleeve 可 qualify),无数据时 DEGRADED + no_market_data。
- `GET /api/quant/factors` 返回注册表;空库启动后 `GET /strategies` 返回 3 条默认策略。
- `conda run -n news-caught python scripts/export_openapi.py` 更新 openapi.json。

## 任务 2(frontend):DeskStockView K 线

文件范围:仅 `frontend/src/views/DeskStockView.vue`、`frontend/src/views/DeskStockView.test.ts`。

验收:K 线卡(日/周)+ A 股资金流面板;`npx vitest run src/views/DeskStockView.test.ts` 绿;不改 KlineChart/FundFlowPanel/client.ts。

## 任务 3(frontend):Desk 仪表盘 + 策略工作台

文件范围:`frontend/src/views/DeskView.vue(+test)`、`frontend/src/views/DeskStrategiesView.vue(+test)`、`frontend/src/stores/deskStore.ts`、`frontend/src/api/client.ts`(加 getQuantFactors)、`frontend/src/api/mock/quant.ts`、`frontend/src/types/`(如需)。

验收:仪表盘分区(覆盖率/漏斗/run 状态/提案权重,纯 CSS)、重跑默认 real、策略页因子表+示例模板;相关 vitest 绿。

## 任务 4(协调者):回填健壮性 + 数据补齐 + 收尾

- `backfill.py` 重试退避、`backfill_main.py` env 参数;重跑 `make quant-backfill` 至 100/100。
- 汇总验证:`conda run -n news-caught pytest backend/tests`、`npm --prefix frontend run build`、`check:api-drift`。
- 更新 `docs/current-state.md`、`docs/code-change-log.md`;归档本设计/计划;显式路径提交。
