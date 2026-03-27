# K 线 Overlay 与 Chart 手势让渡 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore main K-line chart drag / wheel interactions by handing empty-space gestures back to the underlying chart while preserving overlay editing.

**Architecture:** Keep `KlineDrawingOverlay.vue` as the top interaction layer, but add a narrow event handoff path for empty-space `mousedown` / `wheel` in select mode. Reuse existing hit testing to decide whether overlay should keep ownership or temporarily release pointer events to the chart below.

**Tech Stack:** Vue 3, TypeScript, Vitest

---

## Chunk 1: Lock The Regression With Failing Tests

### Task 1: Add overlay handoff tests

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- empty-space `mousedown` in select mode forwarding to the underlying chart element
- `wheel` forwarding in non-editing state
- drawing-body `mousedown` still staying inside overlay and not forwarding

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: FAIL because overlay currently eats all gestures.

## Chunk 2: Implement The Minimal Fix

### Task 2: Add gesture handoff in the overlay

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.vue`

- [ ] **Step 1: Implement empty-space handoff**

Implement:
- hit-test-aware `mousedown` handoff for empty space in select mode
- `wheel` forwarding to the underlying chart
- restore overlay pointer events on global `mouseup`

- [ ] **Step 2: Re-run the overlay test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: PASS.

## Chunk 3: Verify And Log

### Task 3: Verify and record the change

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log immediately after this modification unit**

Append one new top entry covering:
- restored chart gesture handoff
- touched files
- actual verification commands

- [ ] **Step 2: Run focused regressions**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts`
Expected: PASS.

- [ ] **Step 3: Run front-end build**

Run: `npm --prefix frontend run build`
Expected: PASS.
