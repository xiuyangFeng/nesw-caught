# K 线 HUD 浮层下移 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 K 线主图上方的行情 HUD 浮层下移一点，减少对顶部 K 线区域的遮挡，同时保持现有信息和交互不变。

**Architecture:** 只修改 `KlineChart.vue` 的 HUD 定位样式，并用 `KlineChart.test.ts` 锁定新的类名，避免后续 UI 回退。

**Tech Stack:** Vue 3, TypeScript, Vitest, Tailwind CSS

---

## Chunk 1: HUD 定位测试与实现

### Task 1: 为 KlineChart HUD 增加回归断言并调整定位

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: 写失败测试**

验证 `data-role="kline-hud"` 包含新的下移定位类名。

- [ ] **Step 2: 运行单测确认失败**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`

Expected: 旧实现仍保留旧定位类名，因此新断言失败。

- [ ] **Step 3: 写最小实现**

把 `KlineChart.vue` 中 HUD 的垂直定位改为更靠下的一档，其他结构保持不变。

- [ ] **Step 4: 运行单测确认通过**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`

Expected: 组件测试通过。

## Chunk 2: 验证与记录

### Task 2: 更新记录并做构建验证

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: 运行前端构建**

Run: `npm --prefix frontend run build`

Expected: 构建成功。

- [ ] **Step 2: 更新变更记录**

在 `docs/code-change-log.md` 顶部追加本次 HUD 浮层位置调整记录。
