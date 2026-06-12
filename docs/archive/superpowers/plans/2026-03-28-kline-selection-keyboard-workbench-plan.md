# K 线对象工作台键盘增强 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add keyboard-first workbench actions for selected K-line drawings, including delete, escape-to-clear/cancel, and arrow-key multi-selection nudging with undo/redo support.

**Architecture:** Keep keyboard event capture in `KlineChart.vue`, but route durable workbench behavior through `watchlistChartStore.ts`. Extend store actions for batch deletion and nudging of selected drawings, then wire chart-level key guards that avoid interfering with `price_note` label editing and native form inputs.

**Tech Stack:** Vue 3, Pinia, TypeScript, Vitest, lightweight-charts

---

## Chunk 1: Lock The Keyboard Workbench Contract With Failing Tests

### Task 1: Expand store tests for selected-drawing nudging

**Files:**
- Modify: `frontend/src/stores/watchlistChartStore.test.ts`

- [ ] **Step 1: Write the failing tests**

Add assertions for:
- `deleteSelectedDrawings()` removing selected drawings and clearing multi-selection
- `nudgeSelectedDrawings(symbol, { timeStep, priceDelta, candles })` moving every selected drawing
- each nudge creating a history entry that `undo` and `redo` can replay
- when no selected drawing is valid, `nudgeSelectedDrawings()` remains a no-op

- [ ] **Step 2: Run the targeted store test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts`
Expected: FAIL because the store does not yet expose multi-selection keyboard nudge behavior.

### Task 2: Expand chart integration tests for keyboard shortcuts

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`

- [ ] **Step 1: Write the failing tests**

Add assertions for:
- `Delete` deleting the current multi-selection and clearing selection
- `Backspace` deleting the current multi-selection and clearing selection
- `Escape` cancelling draft before clearing selection
- `Escape` clearing selection when no draft is active
- `Arrow` keys nudging all selected drawings
- `Shift + Arrow` using `5` candle / `3%` price-range steps instead of `1` candle / `1%`
- while a drawing draft is active, non-`Escape` editing shortcuts do nothing
- while `price_note` label editing is active, keyboard workbench shortcuts do nothing
- `horizontal_line` ignores left/right nudges but still responds to up/down
- no action firing while an editable input is focused
- overlay `labelEditingChange(true/false)` emitting on open, commit, escape-cancel, and blur
- empty-selection `Backspace` / `Delete` not being intercepted by the global handler

- [ ] **Step 2: Run the targeted chart test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: FAIL because chart-level keyboard shortcuts are not yet wired for delete / escape / nudge.

## Chunk 2: Implement Store Foundation

### Task 3: Add selected-drawing nudge support in the store

**Files:**
- Modify: `frontend/src/stores/watchlistChartStore.ts`
- Modify: `frontend/src/utils/klineOverlayGeometry.ts` (only if existing move helpers need a small extension)

- [ ] **Step 1: Implement the minimal store changes**

Implement:
- `nudgeSelectedDrawings(symbol, { candles, timeStep, priceDelta })`
- history push for each keyboard nudge
- selection preservation after nudge
- no-op guard when there is no valid selection

- [ ] **Step 2: Re-run the targeted store test**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts`
Expected: PASS.

## Chunk 3: Implement Chart Keyboard Wiring

### Task 4: Add chart-level keyboard handlers and guards

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.vue`
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`

- [ ] **Step 1: Implement the minimal chart changes**

Implement:
- `window` keydown subscription / cleanup
- delete, backspace, escape, and arrow-key handling
- focus guards for `input`, `textarea`, `select`, and `contenteditable`
- explicit draft-mode guard so only `Escape` still works
- explicit `price_note` editing guard via overlay-to-chart editing-state signal
- explicit `labelEditingChange(true/false)` lifecycle:
  - open => `true`
  - commit / escape / blur => `false`
- exact nudge contract:
  - left/right = `1` candle, `Shift` 时 `5` candles
  - up/down = full `klineData.candles` range `(maxHigh - minLow) * 0.01`, `Shift` 时 `(maxHigh - minLow) * 0.03`
  - unavailable range fallback to `1`
  - `horizontal_line` left/right = no-op
- empty-selection `Backspace` / `Delete` must fall through without `preventDefault()`

- [ ] **Step 2: Re-run the targeted chart test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: PASS.

## Chunk 4: Verify, Log, Review, And Deliver

### Task 5: Update records and verify the completed slice

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log immediately after this modification unit**

Append one new top entry covering:
- keyboard delete / clear / nudge workbench actions
- touched files
- actual verification commands

- [ ] **Step 2: Run focused regressions**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineDrawingSelectionPopover.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
Expected: PASS.

- [ ] **Step 3: Run front-end build**

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 4: Re-check working tree**

Run: `git status --short`
Expected: only intended files are modified.

- [ ] **Step 5: Request code review and address findings**

Run the repository review flow after implementation and verification, then fix any actionable findings before push.

- [ ] **Step 6: Push and integrate**

Use non-interactive git commands to:
- commit the finished slice with a focused message
- push to `origin/main`
- ensure local `main` reflects the final merged state
