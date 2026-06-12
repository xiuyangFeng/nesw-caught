# K 线指标页中文化与券商式周期 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将自选股详情页 K 线区域的非缩写英文展示改为中文，并把周期入口重构为 `日K / 周K / 月K / 年K` 的券商式语义。

**Architecture:** 保持后端 API 契约不变，仅在前端 store 和组件层整理周期枚举、查询映射与显示文案。`watchlistStore` 负责新的 period-to-query 映射，`StockDetailPanel` 与 `KlineChart` 负责所有用户可见中文标签和摘要信息。

**Tech Stack:** Vue 3, Pinia, TypeScript, Vitest, lightweight-charts

---

## Chunk 1: 周期语义与测试

### Task 1: 更新 watchlistStore 周期映射

**Files:**
- Modify: `frontend/src/stores/watchlistStore.ts`
- Test: `frontend/src/stores/watchlistStore.test.ts`

- [ ] **Step 1: 写失败测试**

在 `watchlistStore.test.ts` 中新增或调整断言，验证：
- 默认周期仍能正常初始化
- `switchPeriod('1D')` 请求 `1d + 1y`
- `switchPeriod('1W')` 请求 `1wk + 5y`
- `switchPeriod('1M')` 请求 `1mo + 10y`
- `switchPeriod('1Y')` 请求 `1mo + max`
- 组件层不再向用户展示 `1D / 1W / 1M / 1Y / 3M` 旧文案

- [ ] **Step 2: 运行单测确认失败**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`

Expected: 与旧映射相关的断言失败。

- [ ] **Step 3: 最小实现**

更新 `PERIOD_QUERY_MAP`，移除旧的 `3M` 语义，确保 `currentInterval/currentRange` 与新映射一致。

- [ ] **Step 4: 运行单测确认通过**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`

Expected: 周期映射相关断言通过。

## Chunk 2: 组件文案中文化与测试

### Task 2: 更新详情页周期入口和顶部摘要中文文案

**Files:**
- Modify: `frontend/src/components/watchlist/StockDetailPanel.vue`
- Test: `frontend/src/components/watchlist/StockDetailPanel.test.ts`

- [ ] **Step 1: 写失败测试**

在组件测试中验证：
- 设置面板展示 `日K / 周K / 月K / 年K`
- 当前激活周期能显示正确中文标签，包含 `年K`
- 顶部摘要中的英文标签已替换成中文
- 加载态与更新时间文案为中文

- [ ] **Step 2: 运行单测确认失败**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts`

Expected: 旧英文/旧周期按钮相关断言失败。

- [ ] **Step 3: 最小实现**

更新 `periods` 来源与展示标签，替换顶部摘要区英文文案。

- [ ] **Step 4: 运行单测确认通过**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts`

Expected: 相关断言通过。

### Task 3: 更新 K 线图摘要、仪表盘和副图区中文文案

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Test: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: 写失败测试**

在 `KlineChart.test.ts` 中验证：
- 摘要标签为中文
- 仪表盘与技术读数中的非缩写英文已中文化
- `VOL` 副图区中的 `Volume / Avg Vol 20 / Close` 改为中文
- 长期视图下的摘要能正确显示 `年K` 对应语义，而不是直接暴露英文范围值

- [ ] **Step 2: 运行单测确认失败**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`

Expected: 旧英文标签相关断言失败。

- [ ] **Step 3: 最小实现**

仅替换用户可见文案与 period 摘要显示，不修改图表数据结构和技术指标缩写。

- [ ] **Step 4: 运行单测确认通过**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`

Expected: 相关断言通过。

## Chunk 3: 集成验证与记录

### Task 4: 完整验证并更新变更记录

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: 运行目标测试集**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts src/views/WatchlistDetailView.test.ts`

Expected: 所有相关测试通过。

- [ ] **Step 2: 运行前端构建**

Run: `npm --prefix frontend run build`

Expected: 构建成功，退出码为 0。

- [ ] **Step 3: 更新变更记录**

在 `docs/code-change-log.md` 顶部追加本轮实际修改、影响文件、验证结果和剩余风险。

- [ ] **Step 4: 复核需求一致性**

确认：
- 缩写未被翻译
- 非缩写英文已中文化
- 周期入口为 `日K / 周K / 月K / 年K`
- 周期按钮语义与实际请求映射一致
