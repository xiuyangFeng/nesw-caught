# K 线常驻周期条与紧凑头部 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 K 线周期切换常驻显示在图表上方，并压缩顶部行情卡片占位，让主图获得更多空间。

**Architecture:** 保持 store 和查询映射不变，只在详情页组件层重排布局。`StockDetailPanel.vue` 负责顶部摘要紧凑化，`KlineChart.vue` 承载新的常驻周期工具条并直接发出 `switchPeriod` 事件。

**Tech Stack:** Vue 3, TypeScript, Vitest, lightweight-charts

---

## Chunk 1: 常驻周期条测试与实现

### Task 1: 在 KlineChart 中增加常驻周期条

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Test: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: 写失败测试**

验证：
- 图表顶部存在 `日K / 周K / 月K / 年K` 常驻按钮
- 当前周期按钮有激活态
- 点击周期按钮会触发 `switchPeriod`

- [ ] **Step 2: 运行单测确认失败**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`

Expected: 因尚未实现常驻周期条和事件透传而失败。

- [ ] **Step 3: 最小实现**

在 `KlineChart.vue` 增加周期工具条，并声明 `currentPeriod`/`switchPeriod` 相关 props/emits。

- [ ] **Step 4: 运行单测确认通过**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`

Expected: 相关断言通过。

## Chunk 2: 顶部卡片紧凑化测试与实现

### Task 2: 压缩 StockDetailPanel 顶部行情卡片并移除重复入口

**Files:**
- Modify: `frontend/src/components/watchlist/StockDetailPanel.vue`
- Test: `frontend/src/components/watchlist/StockDetailPanel.test.ts`

- [ ] **Step 1: 写失败测试**

验证：
- 齿轮按钮不再存在
- `KlineChart` 收到 `currentPeriod`
- 顶部卡片仍渲染核心报价信息和紧凑指标

- [ ] **Step 2: 运行单测确认失败**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts`

Expected: 因旧齿轮入口仍存在而失败。

- [ ] **Step 3: 最小实现**

压缩头部布局，移除齿轮弹层，把周期切换职责完全交给 `KlineChart`。

- [ ] **Step 4: 运行单测确认通过**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts`

Expected: 相关断言通过。

## Chunk 3: 集成验证与记录

### Task 3: 验证详情页并更新记录

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: 运行相关测试**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts src/views/WatchlistDetailView.test.ts`

Expected: 全部通过。

- [ ] **Step 2: 运行前端构建**

Run: `npm --prefix frontend run build`

Expected: 构建成功。

- [ ] **Step 3: 更新变更记录**

在 `docs/code-change-log.md` 顶部追加本轮布局优化记录。
