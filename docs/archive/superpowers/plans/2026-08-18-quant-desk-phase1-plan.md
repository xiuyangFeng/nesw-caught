# 量化交易台 Phase 1 实施计划

- 日期：2026-08-18
- 状态：已完成
- 对应设计：[docs/superpowers/specs/2026-08-18-quant-trading-desk-design.md](../../../superpowers/specs/2026-08-18-quant-trading-desk-design.md) §16 Phase 1
- 前置：Phase 0 已落地 `/desk` 骨架与 PIT 契约

## 目标

建立独立 `market_data.db` 行情地基，补齐 `news_stock_mention` 主链路规则映射，让运行中心能看见数据覆盖，个股页能看见资金流（无数据时合法空态）。

## 本期做

- 独立 SQLite + Alembic（`version_table=alembic_version_market`）：`daily_bar`、`index_daily_bar`、`trade_calendar`、`fund_flow_daily`
- 东财历史 K 线 / 个股资金流解析器（fixture 测试，不在单测里打真实网）
- `make quant-backfill` 分批回填（限速 + 断点）
- 新闻 pipeline 阶段 2 写入 rule mention；短名停用词
- `GET /quant/data/status` 读取真实覆盖率；`GET /quant/symbols/{symbol}/fund-flow`
- `/desk/ops` 数据健康 Tab；个股详情资金流面板

## 本期不做

公司行动全量、龙虎榜/两融采集、公告/财务事实、Parquet 特征、EventRadarWorker、三 sleeve 真实打分。
