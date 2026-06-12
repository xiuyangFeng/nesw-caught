# K 线右侧指标栏折叠 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 K 线右侧指标栏增加一键折叠能力，让主图在需要时获得更大显示面积。

**Architecture:** 仅在 `KlineChart.vue` 内增加本地折叠状态和工具按钮，不改 store 和接口。测试覆盖默认展开、折叠、恢复三个状态。

**Tech Stack:** Vue 3, TypeScript, Vitest, lightweight-charts

---

## Chunk 1: 测试与实现

### Task 1: 为 KlineChart 增加右侧指标栏折叠能力

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Test: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: 写失败测试**

验证：
- 默认显示右侧指标栏
- 点击 `收起面板` 后右侧栏隐藏
- 折叠后布局切换为单列标记
- 点击 `展开面板` 后右侧栏恢复

- [ ] **Step 2: 运行单测确认失败**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`

Expected: 因折叠按钮和状态尚未实现而失败。

- [ ] **Step 3: 最小实现**

在 `KlineChart.vue` 增加本地折叠状态、折叠按钮和响应式布局 class/data-role。

- [ ] **Step 4: 运行单测确认通过**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`

Expected: 相关断言通过。

## Chunk 2: 集成验证与记录

### Task 2: 验证并记录本轮改动

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: 运行相关测试**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts src/views/WatchlistDetailView.test.ts`

Expected: 全部通过。

- [ ] **Step 2: 运行前端构建**

Run: `npm --prefix frontend run build`

Expected: 构建成功。

- [ ] **Step 3: 更新变更记录**

在 `docs/code-change-log.md` 顶部追加本轮折叠面板记录。
