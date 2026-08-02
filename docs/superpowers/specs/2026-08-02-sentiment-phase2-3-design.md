# 情绪模块 Phase 2/3 设计 — 2026-08-02

承接 `2026-08-02-sentiment-eval-revamp-design.md`（Phase 1 已落地，commit b145f84）。本阶段两条线：

- **Phase 2**：回测方法学修复 + 回测结论校准置信度（工作块 E）。
- **Phase 3**：个股情绪时间线 + 情绪-价格背离提醒（后端工作块 G，前端工作块 H）。

公共配置已由主协调者预加进 `app/core/config.py`（`signal_backtest_max_snapshot_age_hours` / `sentiment_confidence_calibration_enabled` / `sentiment_divergence_*`，默认全部保守，不改变旧行为）。**E/G 不要再改 config.py。**

## 已知方法学问题（Phase 1 诊断，作为 E 的需求依据）

1. 回测算的是绝对收益不是超额收益——大盘上涨期 positive 信号命中率被系统性高估。
2. baseline 快照可能是新闻发布前很久的，价格漂移污染收益；无陈旧过滤。
3. 一条新闻提及 N 只股票产生 N 个相关样本，被当独立样本统计。
4. `signal_confidence = 0.35 + |score|*0.5` 只是 |score| 的线性变换，取值 [0.35,0.95]，导致 low 桶（<0.33）恒空；importance 分桶无信息量。

## 工作块 E：回测方法学 + 校准（后端）

**文件所有权**：`app/services/signal_backtest.py`、新 `app/services/sentiment_calibration.py`、`app/schemas/backtest.py`、`app/api/routes/backtest.py`、`app/repositories/news_signal_repository.py`（读取路径按需）、相关测试。**不动** config.py、quote_service.py、news_signal_pipeline.py（校准 hook 例外，见下）、eval 系列文件。

### E1. 超额收益

- 每个样本的 `excess_return = forward_return - benchmark_return`（同 horizon）。
- benchmark 优先级：若 `price_snapshot` 中存在该市场基准指数的快照则用之（E 自行调研库里有没有指数 symbol 约定；大概率没有）；**没有就用「同窗口内全部可评样本的平均 forward_return」作为市场代理基准**，并在响应 `benchmark_note` 中如实说明用的是代理基准。禁止静默假装有真实基准。
- 聚合层新增 `avg_excess_return`（overall + 各桶），旧字段全部保留。

### E2. 陈旧快照过滤

- baseline 快照时间距新闻发布超过 `settings.signal_backtest_max_snapshot_age_hours` → 跳过样本，新计数 `skipped_stale_count`（与既有 `skipped_count` 并列或包含关系，响应里说清楚）。

### E3. 样本相关性

- 新增 `distinct_news_count`；新增 `per_news_hit_rate`：先对每条新闻取其 N 只股票的方向命中均值，再对新闻求均值（每条新闻权重相等）。旧的逐样本 `hit_rate` 保留。

### E4. 分数桶替代 importance 桶

- 新增 `score_buckets: list[ScoreBucketStats]`，按 |sentiment_score| 分桶（建议边界 0.2/0.4/0.6/0.8，E 可微调），字段：`range_label, sample_count, hit_rate, avg_forward_return, avg_excess_return`。
- 旧 `importance` 桶字段保留（兼容前端现状），但在 note 说明其局限。

### E5. 校准（新 `sentiment_calibration.py`）

- `build_calibration(backtest_result | samples) -> SentimentCalibration`：按 score 桶的经验方向命中率生成映射 `mapping: [{score_min, score_max, sample_count, hit_rate, calibrated_confidence}]`（calibrated_confidence = 命中率，样本数 < 30 的桶标记 `low_sample: true` 并回退线性公式值）；并给出 `suggested_positive_threshold` / `suggested_negative_threshold`（最小的、经验命中率 ≥ 0.55 且样本充足的 |score| 桶下界；不存在则 None）。
- 持久化：最新校准写 JSON 文件 `backend/data/research/sentiment_calibration.json`（简单、无迁移；写入原子替换）。
- **响应**：backtest API 响应新增 `calibration: SentimentCalibration | None`（每次回测顺带重算并落盘）。
- **生产 hook（唯一允许动 news_signal_classifier.py 的点，改动最小化）**：`settings.sentiment_confidence_calibration_enabled=True` 时，分类器计算 `signal_confidence` 改查校准映射（文件缺失/桶缺失回退旧线性公式）；默认 False 时代码路径与现状完全一致。加载做模块级懒缓存 + mtime 失效即可。

### E API 变化汇总（`schemas/backtest.py` additive）

`BacktestResponse`（以实际类名为准）新增：`avg_excess_return`、`benchmark_note`、`distinct_news_count`、`per_news_hit_rate`、`skipped_stale_count`、`score_buckets`、`calibration`。旧字段不动。

## 工作块 G：情绪时间线 + 背离提醒（后端）

**文件所有权**：`app/api/routes/watchlist.py`、`app/schemas/watchlist.py`、新 `app/services/sentiment_timeline.py`、新 `app/services/sentiment_divergence.py`、`app/services/notification_service.py`、`app/services/feishu_client.py`、`app/workers/queue_worker.py`（如需注册周期任务）、相关测试。**不动** config.py、main.py、quote_service.py、market 系列（协作者另一条线在改）；若注册点绕不开 main.py，先在结果里说明，不要直接改。

### G1. 情绪时间线 API

`GET /api/watchlist/{symbol}/sentiment-timeline?days=30`（days 默认 30，上限 90）：

```json
{
  "symbol": "AAPL",
  "days": 30,
  "points": [
    {
      "date": "2026-08-01",
      "avg_score": 0.32,
      "news_count": 5,
      "positive_count": 3, "negative_count": 1, "neutral_count": 1,
      "top_news": [ {"id": 1, "title": "...", "sentiment_label": "positive", "sentiment_score": 0.8} ]
    }
  ],
  "divergence": { ...见 G2，无则 null }
}
```

- 数据源：`NewsStockMention` × `NewsItem`（有 sentiment_score 的），按自然日（Asia/Shanghai）聚合；`top_news` 每日按 |score| 取前 3。
- symbol 不在自选股 → 404（与既有 watchlist 详情路由行为一致）。
- 无新闻的日期不补零点（前端自行处理稀疏）。

### G2. 背离检测（`sentiment_divergence.py`）

- `detect_divergence(symbol, window_days, session) -> DivergenceStatus | None`：
  - 窗口 = `settings.sentiment_divergence_window_days`（API 也接受 `?window=` 覆盖，1~14）。
  - `sentiment_avg` = 窗口内该 symbol 新闻 sentiment_score 均值（新闻数 ≥ 3 才判定，否则 None）。
  - `price_change_percent` = price_snapshot 窗口首尾价格变化百分比（快照不足则 None）。
  - 判定：`sentiment_avg ≥ +min_abs_sentiment` 且 `price_change ≤ -min_abs_price_change` → `bearish_divergence`（情绪热价格跌）；反向 → `bullish_divergence`；否则 null。阈值取 settings。
  - 返回字段：`{status, window_days, sentiment_avg, news_count, price_change_percent, detected_at}`。
- 时间线 API 响应内嵌最新判定结果（即时计算）。

### G3. 背离提醒接入通知

- `sentiment_divergence_alert_enabled=True` 时：周期性（复用 `queue_worker.py` 既有周期任务模式，间隔可硬编码 30min）对全部自选股跑 `detect_divergence`，命中则经 `notification_service` 入队 `event_type="sentiment_divergence"`，severity=normal（遵守既有免打扰/去重/合并治理；同 symbol 同方向用既有 latch/去重机制避免重复轰炸，可按「symbol+方向+当日」为 dedupe key）。
- `feishu_client.py` 新增 `build_sentiment_divergence_card`（标题/方向/情绪均值/价格变动/窗口，风格对齐既有卡片），`_build_card_for_job` 加分支。
- 默认关闭 → 零行为变化；测试里显式开启。

## 工作块 H：前端（时间线面板 + 回测视图增强）

**文件所有权**：新 `components/watchlist/SentimentTimelinePanel.vue`（+test）、`views/WatchlistDetailView.vue`（接线）、`views/SignalBacktestView.vue`（+test）、`types/api.ts`、`api/client.ts`、`api/mock*` 相关新增。**不要动** `KlineChart.vue`、`useKlineChartLifecycle.ts`、`watchlistStore.ts`、`AppShell.vue`（协作者在主工作区改这些，尽量减少合并冲突面）。

### H1. SentimentTimelinePanel

- 放进 `WatchlistDetailView.vue`（K 线下方/侧栏合适位置，接线改动保持最小）。
- 内容：近 30 天情绪时间线轻量 SVG 图（正负双色柱或折线，风格参考 `SentimentTrendChart.vue` 的手写 SVG 惯例）+ hover 显示当日 top_news 标题；顶部当前背离状态徽章（`bearish_divergence` 红「情绪-价格背离：情绪偏多但价格走弱」/ `bullish_divergence` 绿、null 不显示）；空态文案。
- 数据：`apiClient.getSentimentTimeline(symbol, days)`（新增），组件内自取数（不进 watchlistStore，避免碰协作者文件）。

### H2. SignalBacktestView 增强

- additive 展示：`avg_excess_return`（与绝对收益并列，标注 benchmark_note）、`per_news_hit_rate` 与 `distinct_news_count`、`skipped_stale_count`、`score_buckets` 表格（替代性地放在 importance 桶旁边，注明「按情绪分数分桶」）、`calibration` 区块（映射表 + 建议阈值，低样本桶灰显）。
- 旧区块不删。

### H3. types/mock

- `types/api.ts` additive 手写类型（同 Phase 1 模式）；`api/client.ts` 新增 `getSentimentTimeline`；mock 夹具含背离/无背离/空数据三态。

## 验证要求（全部工作块）

- 后端：TDD；`conda run -n news-caught pytest backend/tests/<相关> -q` 全绿；不破坏既有测试（5 个硬编码路径的预存在失败除外）。
- 前端：相关测试 + `npm --prefix frontend run build` 通过。
- 不改 `docs/code-change-log.md`（主协调者统一回填）；不 git commit；越界需求写进结果而不是直接改。
