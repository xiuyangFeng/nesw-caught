# K 线十字光标与画线编辑增强 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a synthetic chart crosshair with time/price labels plus basic post-selection editing for core drawing tools in the watchlist K-line workbench.

**Architecture:** Keep overlay-driven interaction as the single pointer/event layer. Extend `klineOverlayGeometry.ts` for crosshair projection and drawing edit math, teach `KlineDrawingOverlay.vue` to render crosshair lines/labels and emit edit commits, and wire those events into `KlineChart.vue` using the existing chart store update actions.

**Tech Stack:** Vue 3, TypeScript, Pinia, Vitest, lightweight-charts, Tailwind utility classes

---

## Chunk 1: Lock The New Interaction Contract With Failing Tests

### Task 1: Add failing geometry tests

**Files:**
- Create: `frontend/src/utils/klineOverlayGeometry.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- nearest-candle index lookup from pixel x position
- anchor-handle hit testing
- moving a trend line and a rectangle while preserving relative shape
- moving a horizontal line by price only
- crosshair projection output for time/price labels

- [ ] **Step 2: Run the geometry test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts`
Expected: FAIL because the helper functions do not exist yet.

### Task 2: Add failing overlay interaction tests

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- crosshair lines and labels appearing after mousemove
- selected drawing rendering anchor handles
- dragging an anchor emitting `drawing-anchor-commit`
- dragging a selected object body emitting `drawing-move-commit`
- locked drawings remaining selectable but not draggable

- [ ] **Step 2: Run the overlay test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: FAIL because the overlay does not yet render/edit with this contract.

### Task 3: Add failing chart integration tests

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: Write the failing test**

Add assertions for:
- overlay edit commit events calling through to the selected drawing state path
- hover/edit state resetting correctly when chart props change

- [ ] **Step 2: Run the chart test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: FAIL because the chart does not yet consume the new overlay edit events. Real crosshair label assertions stay in `KlineDrawingOverlay.test.ts`, since `KlineChart.test.ts` currently mocks the overlay component.

## Chunk 2: Implement Crosshair And Drawing Edit

### Task 4: Implement geometry helpers

**Files:**
- Modify: `frontend/src/utils/klineOverlayGeometry.ts`

- [ ] **Step 1: Implement the minimal pure helpers**

Implement:
- candle index lookup from pixel
- anchor hit testing with radius threshold
- drawing move helpers for trend line / horizontal line / price range
- crosshair projection output containing snapped time, x, y, and formatted label inputs

- [ ] **Step 2: Re-run the geometry test**

Run: `npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts`
Expected: PASS.

### Task 5: Implement overlay crosshair and editing

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.vue`

- [ ] **Step 1: Implement crosshair and selected-anchor rendering**

Implement:
- crosshair line rendering driven by hover anchor
- time and price label rendering
- anchor handles for selected drawings

- [ ] **Step 2: Implement drag commit behavior**

Implement:
- anchor drag commit emission
- object move commit emission
- locked-object no-drag guard

- [ ] **Step 3: Re-run the overlay test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: PASS.

### Task 6: Wire chart integration

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: Wire new overlay edit events into the store**

Implement:
- calling `updateDrawingAnchors` on anchor commit
- calling `moveDrawing` on move commit
- resetting hover/edit state when symbol or candle set changes
- extending the overlay mock in `KlineChart.test.ts` so commit events can be triggered and asserted against store state

- [ ] **Step 2: Re-run the chart test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: PASS.

## Chunk 3: Regression Verification And Logging

### Task 7: Run focused regressions and log the work

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused regressions**

Run: `npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
Expected: PASS.

- [ ] **Step 1.5: Update the code change log for this modification unit**

Append one new top entry to `docs/code-change-log.md` immediately after this slice is implemented and verified; do not defer logging to a later unrelated batch.

- [ ] **Step 2: Run frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 3: Re-check working tree**

Run: `git status --short`
Expected: only intended files are modified.
