# 量化交易台补全:真实选票流水线 + K线/仪表盘/策略可见性(设计)

日期:2026-08-18 · 作者:Claude · 状态:实施中

## 背景与问题

Phase 0~5 落地后,交易台四处"看不到东西",根因经侦察确认:

1. **不能选票**:`POST /api/quant/recommendations/run` 只跑 `run_synthetic_pipeline`,候选是 `fixtures/synthetic.py` 硬编码的 3 只;`factors.py` 的三 sleeve 打分函数(`score_event/score_trend/score_fundamental`)在生产链路无任何调用点;`recommendation_run` 表 0 行(从未跑过)。
2. **看不到 K 线**:`DeskStockView.vue` 无任何图表组件;`components/watchlist/KlineChart.vue`(lightweight-charts)与 `GET /api/market/symbols/{symbol}/kline` 均可直接复用。
3. **看不到仪表盘**:`/dashboard` 是新闻舆情盘;desk 系列只有纯文字状态条,无图形化总览。
4. **看不到策略**:`quant_strategy` 空表起步,无默认策略、无因子注册表展示,页面是裸 DSL 编辑器。

另:`market_data.db` 今日首次回填,东财限流导致仅 29/100 只完成(有断点续传);无每日增量 worker。

## 方案

### A. 真实选票流水线(backend)

新增 `app/services/quant/recommendation/market_pipeline.py`,`run_market_pipeline(*, versions) -> PipelineResult`,并在 `PipelineScenario` 增加 `REAL = "real"`;`QuantDeskService.run` 按 scenario 分发,`QuantRunRequest.scenario` 默认改为 `"real"`(`abstain/mixed` 保留用于测试/演示)。

流水线阶段(全部确定性,LLM 不参与):

1. **data_gate**:读 `market_data.db`。无 daily_bar → `RunStatus.DEGRADED` + `empty_reason="no_market_data"`,detail 提示执行 `make quant-backfill`;有数据但 `last_trade_date` 落后今天 > 5 个自然日 → stage 记 stale 警告,继续跑。
2. **universe_u2**(真实数据近似,不再用 synthetic_master):
   - 该 symbol 的 bar 历史条数 ≥ 120(上市时长近似);
   - 20 日中位成交额 ≥ 1e8(复用 `DEFAULT_MIN_MEDIAN_AMOUNT_20D`);
   - 最新交易日有 bar(排除停牌/数据陈旧个股)。
3. **三 sleeve 打分**(复用 `factors.py`,不改其阈值):
   - `trend_flow`:`score_trend(inflow=该股最新 main_net_inflow, adv=20 日均成交额)`;breakdown 追加 `ret_20d`(20 日收益,只作展示证据)。
   - `event_catalyst`:近 7 日主库 `NewsStockMention`(rule)聚合 → `novelty` 按最近提及日衰减(1 - days/7),`materiality=min(1, count/3)`,grade 取 `"C"`(规则命中证据弱,按 `score_event` 设计天然不 qualify,只进 WATCH——诚实优先,不给规则 mention 发 A/B)。若无 mention 则该 sleeve 不产生候选。
   - `fundamental_revalue`:`score_fundamental(gap="no_financials")`,显式 gap,不合格(财务数据未采购,不编造)。
4. **交易规则闸门**:qualified 候选若最新 bar 开盘触涨停(`is_limit_up_open`,板块按代码前缀映射 Board)→ 降级 WATCH,reason `limit_up_open_unfillable`。
5. **状态机/排名/哈希**:复用 `candidate.transition`(DISCOVERED→VALIDATING→WATCH/QUALIFIED)、按 score 排 rank、`compute_result_hash`。
6. **versions**:`dataset_version=f"eastmoney-daily-{last_trade_date}"`、`factor_version="rule-v1"`、`source_cutoff=now(UTC)`。

组合提案 `get_proposal` 现已从 latest qualified 派生,无需改动;`allocate` 的 vol 参数用 20 日日收益标准差(无则 1.0)。

### B. 默认策略与因子可见性(backend)

- 新端点 `GET /api/quant/factors`:返回 `FACTOR_REGISTRY`(key/sleeve/horizon)。
- 启动种子:`seed_demo_data=True` 且 `quant_strategy` 空表时,插入 3 条探索性默认策略(每 sleeve 一条,DSL 只引用注册表内因子,`is_active=0`、exploratory)。幂等:表非空即跳过。

### C. 前端补全

- **DeskStockView**:顶部加 K 线卡(复用 `KlineChart` + `apiClient.getStockKline`,日/周切换),A 股再挂 `FundFlowPanel`(quant fund-flow 接口已有);研究包区保留。
- **DeskView**:状态带下方新增「交易台仪表盘」分区:数据覆盖率进度条、三 sleeve 漏斗横条(qualified/watch)、最近 run 状态与耗时、组合提案权重条 + 现金占比。纯 CSS/SVG,不引入新图表库;空数据显示合法空态。「手动重跑」默认发 `scenario="real"`。
- **DeskStrategiesView**:上方加「因子注册表」表格(新 client 方法 `getQuantFactors` + mock 兜底);「填入示例」按钮写入模板 DSL;列表展示种子默认策略。

### D. 回填健壮性(backend,小改)

- `backfill.py`:每 symbol 抓取失败重试 3 次,指数退避(2s/8s/30s)。
- `backfill_main.py`:支持 env `QUANT_BACKFILL_LIMIT`(默认 100)、`QUANT_BACKFILL_SLEEP`(默认 0.2)、`QUANT_BACKFILL_DAYS`(默认 1095)。

## 边界与不做

- 不采购财务/一致预期数据;fundamental sleeve 保持显式 gap。
- 不做每日自动增量行情 worker(列为后续事项)。
- 不改 `factors.py` 阈值、allocator 约束(单票 ≤8%、现金 ≥10%)、回测/模拟盘链路。
- LLM 仍不参与排名/仓位。

## 风险

- 东财接口无 SLA,限流已实测发生;回填靠断点续传+退避缓解。
- rule mention 证据弱,event sleeve 只产 WATCH 是设计而非缺陷。
- 覆盖率 <100% 时选票只在已回填池内进行,data_status 如实展示覆盖率。
