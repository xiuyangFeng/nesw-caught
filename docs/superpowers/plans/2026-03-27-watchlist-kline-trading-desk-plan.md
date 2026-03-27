# Watchlist Kline Trading Desk Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 watchlist 详情区改造成交易台式三段 K 线面板，提升主图优先级和行情扫描效率，同时保留新闻联动。

**Architecture:** 维持现有 `WatchlistView -> StockDetailPanel -> KlineChart / IndicatorChart / RelatedNewsSidebar` 数据流，不改后端接口，只重构右侧详情区的结构和样式。通过先写失败测试锁定新布局和关键 data-role，再做最小实现并补充样式细化。

**Tech Stack:** Vue 3, Pinia, TypeScript, Tailwind utility classes, Vitest, lightweight-charts

---

## Chunk 1: 交易台布局测试与骨架

### Task 1: 锁定交易台顶层结构

**Files:**
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/components/watchlist/StockDetailPanel.vue`
- Test: `frontend/src/views/WatchlistView.test.ts`

- [ ] **Step 1: 写失败测试，验证新的交易台关键区域存在**

在 `frontend/src/views/WatchlistView.test.ts` 中新增断言，至少覆盖：
- `data-role="trading-desk-summary"`
- `data-role="trading-desk-main"`
- `data-role="trading-desk-secondary"`
- 顶部摘要出现股票名/代码、最新价、涨跌额、涨跌幅、开盘、昨收、最高、最低、成交量、更新时间
- 周期切换按钮仍出现在顶部摘要区而不是下沉到其他面板

- [ ] **Step 2: 运行单测并确认因新结构缺失而失败**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: FAIL，提示缺少新的 `data-role` 或文案

- [ ] **Step 3: 在 `StockDetailPanel.vue` 中实现新的三段式布局骨架**

要求：
- 详情区改成顶部摘要、中部主图、底部辅助区三段
- 周期按钮放入顶部摘要区
- 保留现有 indicator/news 联动状态

- [ ] **Step 4: 重新运行单测确认通过**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: PASS

## Chunk 2: 主图交易面板

### Task 2: 锁定主图摘要、图例和事件筹码条

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Test: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: 写失败测试，验证主图交易面板新增元素**

在 `frontend/src/components/watchlist/KlineChart.test.ts` 中新增断言，至少覆盖：
- `data-role="kline-chart-legend"`
- `data-role="kline-chart-summary"`
- `data-role="kline-event-chip-2026-03-19"`
- 默认 MA5/10/20/60 图例全部可见
- 若存在 `bollinger` 数据，图例中能看到 BOLL 标识
- 当 `klineData` 为空时保留空态骨架

- [ ] **Step 2: 运行单测并确认失败**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: FAIL，提示新元素不存在

- [ ] **Step 3: 在 `KlineChart.vue` 中实现主图交易面板**

要求：
- 增加主图标题栏、overlay 图例、摘要信息条
- 默认保持 `MA5/10/20/60` 主图叠加线可见
- 若存在布林带数据，在图例中展示 BOLL 可用状态
- 将新闻事件按钮重构为更紧凑的事件筹码条
- 空数据时不移除整个主图骨架

- [ ] **Step 4: 重新运行单测确认通过**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: PASS

## Chunk 3: 副图区与新闻时间流

### Task 3: 完成辅助区交易台风格

**Files:**
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/components/watchlist/IndicatorChart.vue`
- Modify: `frontend/src/components/watchlist/RelatedNewsSidebar.vue`
- Modify: `frontend/src/components/watchlist/StockDetailPanel.vue`
- Test: `frontend/src/views/WatchlistView.test.ts`

- [ ] **Step 1: 写失败测试，锁定新闻时间流和辅助区布局**

在 `frontend/src/views/WatchlistView.test.ts` 中新增断言，至少覆盖：
- `data-role="trading-desk-news-feed"`
- `data-role="trading-desk-signal-card"`
- 新闻项显示来源和情绪
- 点击事件筹码条后，对应新闻项出现高亮状态
- 点击新闻项后，对应日期高亮保持可见

- [ ] **Step 2: 运行单测并确认失败**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: FAIL，提示新的辅助区结构不存在

- [ ] **Step 3: 实现副图区和新闻时间流改造**

要求：
- `IndicatorChart.vue` 调整为更接近终端页签风格
- `RelatedNewsSidebar.vue` 改造成时间流式新闻区
- `StockDetailPanel.vue` 补简洁 signal summary，并明确保持次级视觉权重
- 新闻区视觉密度弱于顶部行情摘要和主图区，避免重新抢主视觉

- [ ] **Step 4: 重新运行相关单测确认通过**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: PASS

## Chunk 4: 集成验证与记录

### Task 4: 完成集成验证和文档更新

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: 运行本轮相关前端测试**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/components/watchlist/KlineChart.test.ts src/stores/watchlistStore.test.ts`
Expected: PASS

- [ ] **Step 2: 运行前端构建验证**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 3: 更新代码变更记录**

在 `docs/code-change-log.md` 顶部追加本轮记录，明确写出：
- 交易台式三段结构
- 主图摘要/图例/事件筹码条
- 新闻时间流改造
- 验证命令

- [ ] **Step 4: 自检完成后再进入 code review**

要求：
- 确认未改后端接口
- 确认移动端仍可自然折叠
- 确认无未使用状态或明显重复样式
- 确认主图仍是最强视觉焦点，新闻区和 signal summary 没有回到主屏主角位置
