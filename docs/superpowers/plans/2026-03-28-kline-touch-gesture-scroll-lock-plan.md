# K 线触摸手势滚动穿透修复 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop page scrolling when the user swipes inside the K-line chart by extending overlay gesture handoff to touch interactions without breaking drawing editing.

**Architecture:** Keep `KlineDrawingOverlay.vue` as the top interaction layer and extend the existing empty-space gesture handoff path from mouse-only to touch. Touch handoff should activate only in select mode on blank space, preserve ownership for drawing hits or editing states, and explicitly constrain browser default scroll behavior while the chart is consuming the gesture.

**Tech Stack:** Vue 3, TypeScript, Vitest

---

## Chunk 1: Lock The Regression With Failing Tests

### Task 1: Add touch handoff regression tests

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- empty-space `touchstart` / `touchmove` / `touchend` forwarding to the underlying chart element
- touch handoff keeping browser scroll suppression active only while the chart gesture path is active
- touch session cleanup restoring overlay ownership after `touchend` / `touchcancel`
- drawing-body touch press and non-`select` or editing states staying inside overlay and not forwarding

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: FAIL because the overlay currently has no touch handoff behavior.

## Chunk 2: Implement The Minimal Fix

### Task 2: Add touch gesture handoff in the overlay

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.vue`

- [ ] **Step 1: Implement touch-aware empty-space handoff**

Implement:
- touch event normalization for hit testing and point lookup
- blank-space `touchstart` handoff to the underlying chart element
- forwarding `touchmove` / `touchend` / `touchcancel` to the same underlying target for a complete gesture sequence
- touch session cleanup on `touchend` / `touchcancel`
- explicit non-passive `touchmove.preventDefault()` only for the chart gesture path
- state guards preserving overlay ownership for non-`select`, dragging, or label-editing states

- [ ] **Step 2: Re-run the overlay test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: PASS.

## Chunk 3: Verify And Log

### Task 3: Verify and record the change

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log immediately after this modification unit**

Append one new top entry covering:
- restored touch gesture handoff inside the K-line chart
- prevented chart-region swipe from scrolling the full page
- touched files
- actual verification commands

- [ ] **Step 2: Run focused regressions**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts`
Expected: PASS.

- [ ] **Step 3: Run front-end build**

Run: `npm --prefix frontend run build`
Expected: PASS.
