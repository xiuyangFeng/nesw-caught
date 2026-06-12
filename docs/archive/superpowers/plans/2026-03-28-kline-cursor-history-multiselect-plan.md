# K 线统一游标、撤销重做与多选工具条 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the K-line workbench into a more durable analysis tool by adding unified cursor state, per-symbol undo/redo, and shift-based multi-selection with a richer object toolbar.

**Architecture:** Keep overlay-driven editing, but move durable workbench state into `watchlistChartStore.ts`. `KlineChart.vue` becomes the integration point for cursor state and action wiring, while `KlineDrawingOverlay.vue`, `KlineToolbar.vue`, and `KlineDrawingSelectionPopover.vue` emit narrow interaction events.

**Tech Stack:** Vue 3, Pinia, TypeScript, Vitest, lightweight-charts

---

## Chunk 1: Lock Store And UI Contracts With Failing Tests

### Task 1: Add failing store tests for history and multi-selection

**Files:**
- Modify: `frontend/src/stores/watchlistChartStore.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- selecting one drawing vs `Shift+Click` toggling multi-selection
- `undo` restoring the previous drawings snapshot
- `redo` restoring the undone snapshot
- new edits clearing the redo stack
- group delete / duplicate / lock / visible toggle acting on all selected drawings

- [ ] **Step 2: Run the targeted store test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts`
Expected: FAIL because the store has no history or multi-selection contract yet.

### Task 2: Add failing toolbar and popover tests

**Files:**
- Modify: `frontend/src/components/watchlist/KlineToolbar.test.ts`
- Create: `frontend/src/components/watchlist/KlineDrawingSelectionPopover.test.ts`

- [ ] **Step 1: Write the failing tests**

Add assertions for:
- undo / redo buttons rendered, disabled state respected, and events emitted
- popover single-select actions still work
- popover multi-select mode exposes group actions and selection count

- [ ] **Step 2: Run the targeted component tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineDrawingSelectionPopover.test.ts`
Expected: FAIL because the components do not yet expose these controls.

### Task 3: Add failing overlay and chart integration tests

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: Write the failing tests**

Add assertions for:
- `Shift+Click` causing additive selection instead of replacement
- blank click clearing current selection
- toolbar undo / redo events calling store actions
- multi-select toolbar group delete / lock actions writing back to drawings

- [ ] **Step 2: Run the targeted integration tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts`
Expected: FAIL because chart / overlay still assume single selection and lack history wiring.

## Chunk 2: Implement Store Foundation

### Task 4: Extend the chart store

**Files:**
- Modify: `frontend/src/stores/watchlistChartStore.ts`
- Modify: `frontend/src/types/api.ts` (only if a cursor/selection helper type is needed)

- [ ] **Step 1: Implement multi-selection and history**

Implement:
- `selectedDrawingIds`
- `selectDrawing(id, options?)`
- `clearSelection()`
- `canUndo` / `canRedo`
- `undo(symbol)` / `redo(symbol)`
- internal drawings snapshot push / restore

- [ ] **Step 2: Implement group actions**

Implement:
- `deleteSelectedDrawings`
- `duplicateSelectedDrawings`
- `toggleSelectedLocked`
- `toggleSelectedVisible`
- selection cleanup after delete / symbol change

- [ ] **Step 3: Re-run the store test**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts`
Expected: PASS.

## Chunk 3: Implement UI Controls

### Task 5: Add undo/redo toolbar controls

**Files:**
- Modify: `frontend/src/components/watchlist/KlineToolbar.vue`
- Modify: `frontend/src/components/watchlist/KlineToolbar.test.ts`

- [ ] **Step 1: Implement the toolbar controls**

Implement:
- undo / redo buttons
- disabled states
- `undo` / `redo` emits

- [ ] **Step 2: Re-run the toolbar test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts`
Expected: PASS.

### Task 6: Upgrade the selection popover into an object toolbar

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingSelectionPopover.vue`
- Create: `frontend/src/components/watchlist/KlineDrawingSelectionPopover.test.ts`

- [ ] **Step 1: Implement single and multi-select modes**

Implement:
- `selectedDrawings` input
- single-select style controls
- multi-select group actions
- selection count copy

- [ ] **Step 2: Re-run the popover test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingSelectionPopover.test.ts`
Expected: PASS.

## Chunk 4: Wire Overlay And Chart

### Task 7: Implement additive selection in the overlay

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.vue`
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`

- [ ] **Step 1: Implement selection modifier semantics**

Implement:
- selection payload carrying `append`
- blank click clearing selection
- keep primary-object anchors on the first selected drawing only

- [ ] **Step 2: Re-run the overlay test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: PASS.

### Task 8: Wire chart-level history, cursor, and group actions

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: Implement the integration**

Implement:
- toolbar undo / redo hooks
- overlay selection append handling
- object-toolbar group actions
- unified cursor state fallback so HUD remains correct after undo/redo and selection changes

- [ ] **Step 2: Re-run the chart test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: PASS.

## Chunk 5: Verify, Log, And Deliver

### Task 9: Verify and record each completed modification unit

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log after each completed slice**

At minimum append entries for:
- store history + multi-selection foundation
- UI wiring for toolbar / object toolbar / chart integration

- [ ] **Step 2: Run focused regressions**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineDrawingSelectionPopover.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
Expected: PASS.

- [ ] **Step 3: Run front-end build**

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 4: Re-check working tree**

Run: `git status --short`
Expected: only intended files are modified.

- [ ] **Step 5: Commit locally on `main`**

Use non-interactive git commands with focused commit messages for the completed slices.
