# K 线画线与指标工作台 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the watchlist K-line module into a local-first workbench with drawing tools, persistent per-symbol drawings, and global indicator templates.

**Architecture:** Keep `watchlistStore` as the single source of symbol/period/market data. Add a new `watchlistChartStore` plus pure utility modules for drawing schema, overlay geometry, indicator template persistence, and front-end EMA/RSI calculation. `KlineChart.vue` becomes a composition shell around toolbar, drawing overlay, indicator workbench, and the existing lightweight-charts renderers.

**Tech Stack:** Vue 3, Pinia, Vitest, lightweight-charts, TypeScript, localStorage

---

## Chunk 1: Data Contracts And Store Foundation

### Task 1: Lock the data model with failing utility tests

**Files:**
- Create: `frontend/src/utils/klineDrawings.test.ts`
- Create: `frontend/src/utils/klineIndicatorTemplates.test.ts`
- Create: `frontend/src/utils/klineIndicators.test.ts`
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Write the failing tests**

Add tests that cover:
- drawing object serialization for `trend_line`, `horizontal_line`, `price_range`, `fibonacci_retracement`, `price_note`
- `price_note.payload.text` persistence and empty-label fallback
- template validation, active-template fallback to `经典均线`, invalid params rejection
- versioned localStorage payload restoration, `version = 0` template migration, and active-template key recovery
- drawing payload version migration and hydration fallback
- EMA and RSI calculation from candles

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/utils/klineDrawings.test.ts src/utils/klineIndicatorTemplates.test.ts src/utils/klineIndicators.test.ts`
Expected: FAIL because the utility modules and new types do not exist yet.

- [ ] **Step 3: Add the missing frontend contracts**

Update `frontend/src/types/api.ts` with:
- drawing tool types
- drawing object schema
- indicator template types
- overlay indicator param types
- active template identifiers

- [ ] **Step 4: Implement the utility modules**

Create:
- `frontend/src/utils/klineDrawings.ts`
- `frontend/src/utils/klineIndicatorTemplates.ts`
- `frontend/src/utils/klineIndicators.ts`

Implement:
- default drawing styles
- drawing serialization / deserialization
- template validation and fallback logic
- localStorage read/write helpers
- EMA/RSI calculators and template-to-render-config mapping
- a canonical preset-template catalogue containing `经典均线` / `趋势跟随` / `震荡观察` / `强弱判断`

- [ ] **Step 5: Re-run the utility tests**

Run: `npm --prefix frontend run test -- --run src/utils/klineDrawings.test.ts src/utils/klineIndicatorTemplates.test.ts src/utils/klineIndicators.test.ts`
Expected: PASS.

### Task 2: Add geometry helpers for hit testing and anchor movement

**Files:**
- Create: `frontend/src/utils/klineOverlayGeometry.ts`
- Create: `frontend/src/utils/klineOverlayGeometry.test.ts`

- [ ] **Step 1: Write the failing geometry tests**

Add tests for:
- nearest candle time snapping
- all five drawing tools hit testing
- anchor updates and whole-object movement
- fallback time remapping across aggregated candles, including exact-match / nearest-earlier / first-candle / last-candle cases
- re-projection inputs needed after chart resize or visible-range changes

- [ ] **Step 2: Run the targeted test**

Run: `npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts`
Expected: FAIL because the geometry helper does not exist.

- [ ] **Step 3: Implement the geometry helper**

Implement pure functions for:
- candle time remapping
- pixel-space projection input shape
- object hit testing
- drag delta application

- [ ] **Step 4: Re-run the geometry test**

Run: `npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts`
Expected: PASS.

### Task 3: Build the chart workbench store behind tests

**Files:**
- Create: `frontend/src/stores/watchlistChartStore.ts`
- Create: `frontend/src/stores/watchlistChartStore.test.ts`

- [ ] **Step 1: Write the failing store tests**

Add tests for:
- hydrating drawings for a symbol
- selecting a tool and starting/canceling/committing drafts
- deleting drawings
- applying templates and falling back when the active template is deleted
- persisting drawings per symbol and templates globally
- disabling edits when there is no candle data

- [ ] **Step 2: Run the store test**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts`
Expected: FAIL because the store does not exist.

- [ ] **Step 3: Implement the store**

Implement:
- single source of truth for active tool, draft, selected drawing, templates, sub-indicator
- hydration from localStorage
- symbol-scoped drawing persistence
- active-template fallback
- editing state transitions for draft / label edit / drag commit
- debounced persistence timing plus `beforeunload` flush wiring
- public actions from the spec contract:
  - `hydrateForSymbol`
  - `selectTool`
  - `startDraft`
  - `updateDraft`
  - `commitDraft`
  - `cancelDraft`
  - `selectDrawing`
  - `updateDrawingAnchors`
  - `moveDrawing`
  - `updateDrawingStyle`
  - `commitLabelEdit`
  - `deleteDrawing`
  - `clearSymbolDrawings`
  - `toggleDrawingLocked`
  - `toggleDrawingVisible`
  - `applyTemplate`
  - `saveCustomTemplate`
  - `deleteCustomTemplate`
  - `setSubIndicator`

- [ ] **Step 4: Re-run the store test**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistChartStore.test.ts`
Expected: PASS.

## Chunk 2: UI Components And Kline Integration

### Task 4: Build the toolbar and indicator workbench from failing component tests

**Files:**
- Create: `frontend/src/components/watchlist/KlineToolbar.vue`
- Create: `frontend/src/components/watchlist/KlineToolbar.test.ts`
- Create: `frontend/src/components/watchlist/KlineIndicatorWorkbench.vue`
- Create: `frontend/src/components/watchlist/KlineIndicatorWorkbench.test.ts`
- Create: `frontend/src/components/watchlist/KlineDrawingSelectionPopover.vue`
- Create: `frontend/src/components/watchlist/KlineDrawingSelectionPopover.test.ts`

- [ ] **Step 1: Write the failing component tests**

Add tests for:
- period chips + drawing tool chips
- disabled tool state when no candles exist
- template apply / save / delete emissions
- sub-indicator switching through the workbench
- copy-template and reset-to-default controls
- visible current-template name / summary / template-library state
- selected-object floating controls for color / line width / dash / lock / delete

- [ ] **Step 2: Run the component tests**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts`
Expected: FAIL because the components do not exist.

- [ ] **Step 3: Run the selection popover test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingSelectionPopover.test.ts`
Expected: FAIL because the popover component does not exist.

- [ ] **Step 4: Implement the components**

Implement compact terminal-style UI that matches the existing watchlist detail chrome and emits:
- `period-change`
- `tool-change`
- `clear-drawings`
- `template-apply`
- `template-save`
- `template-delete`
- `subindicator-change`
- `style-change`
- `drawing-lock-toggle`
- `drawing-delete`

Define reset behavior explicitly as:
- clicking “重置为默认” triggers the same apply flow as `template-apply('经典均线')`

Define copy behavior explicitly as:
- clicking “复制模板” clones the currently active template into a new custom-template payload
- the workbench then reuses the existing `template-save` path with that cloned payload
- the new template gets a fresh id and a default derived name such as `<原模板名>-副本`

- [ ] **Step 5: Re-run the component tests**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts`
Expected: PASS.

- [ ] **Step 6: Re-run the selection popover test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingSelectionPopover.test.ts`
Expected: PASS.

### Task 5: Build the drawing overlay with interaction tests

**Files:**
- Create: `frontend/src/components/watchlist/KlineDrawingOverlay.vue`
- Create: `frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`

- [ ] **Step 1: Write the failing overlay tests**

Add tests for:
- rendering persisted objects
- select-mode click choosing top-most object
- trend line creation via two clicks
- horizontal line creation via single click
- rectangle creation via drag
- fibonacci retracement creation via two clicks and level rendering
- price-note label edit emission
- `Esc` exits drawing mode and cancels draft
- `Delete/Backspace` removes the selected object
- locked objects remain selectable but cannot be dragged
- resize / visible-range change triggers re-projection
- dragging pauses chart-pan ownership while edit is active
- empty-space click in select mode falls through to chart ownership
- disabled mode when `klineData` is absent

- [ ] **Step 2: Run the overlay test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: FAIL because the overlay component does not exist.

- [ ] **Step 3: Implement the overlay**

Implement:
- SVG or canvas overlay rendering
- hit testing delegation to geometry helpers
- draft previews
- select / drag / label edit emissions
- keyboard interaction for `Esc` and `Delete/Backspace`
- locked-object drag prevention
- re-projection on resize and visible-range changes
- temporary drag ownership so chart panning pauses during edit drags
- select-mode empty-space passthrough so chart hover/crosshair behavior remains intact
- disabled and empty-candle behavior

- [ ] **Step 4: Re-run the overlay test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: PASS.

### Task 6: Integrate the new workbench into `KlineChart` and update regressions

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`
- Modify: `frontend/src/components/watchlist/StockDetailPanel.test.ts`
- Modify: `frontend/src/views/WatchlistDetailView.test.ts`

- [ ] **Step 1: Expand the failing regressions**

Add assertions for:
- toolbar and workbench rendering inside `KlineChart`
- template-driven sub-indicator state
- overlay disabled state when `klineData` is null
- no-data disabled behavior for template application
- selection popover controls and selected-object actions
- template copy and reset wiring
- continued `focusNews` and `switchPeriod` behavior

- [ ] **Step 2: Run the focused regression suite**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
Expected: FAIL because the old chart shell does not include the workbench pieces.

- [ ] **Step 3: Refactor `KlineChart.vue`**

Refactor the component so it:
- keeps lightweight-charts rendering for candles and existing indicators
- replaces local `activeSubIndicator` state with `watchlistChartStore`
- mounts `KlineToolbar`, `KlineDrawingOverlay`, and `KlineIndicatorWorkbench`
- mounts `KlineDrawingSelectionPopover`
- rehydrates drawings for the current symbol and current candles
- wires `clear-drawings` from `KlineToolbar` to `watchlistChartStore.clearSymbolDrawings(currentSymbol)`
- wires selected-object style / lock / delete actions
- wires template copy / reset actions
- keeps the existing news event chips and period switching contract intact

- [ ] **Step 4: Re-run the focused regression suite**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
Expected: PASS.

### Task 7: Verify the full watchlist path and document the change

**Files:**
- Modify: `frontend/src/stores/watchlistStore.test.ts`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Add or update watchlist store regression coverage if integration assumptions changed**

Keep the current symbol / period ownership contract intact and add tests only if `KlineChart` integration requires new watchlist behavior.

- [ ] **Step 2: Run the complete targeted frontend suite**

Run: `npm --prefix frontend run test -- --run src/utils/klineDrawings.test.ts src/utils/klineOverlayGeometry.test.ts src/utils/klineIndicatorTemplates.test.ts src/utils/klineIndicators.test.ts src/stores/watchlistChartStore.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts src/stores/watchlistStore.test.ts`
Expected: PASS.

- [ ] **Step 3: Run the production build**

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 4: Update the change log**

Append a top entry to `docs/code-change-log.md` that records:
- the drawing overlay workbench
- template system and front-end EMA/RSI support
- affected files
- verification evidence
- residual risks such as no undo/redo and no multi-tab merge

---

Plan complete and saved to `docs/superpowers/plans/2026-03-27-kline-drawing-indicator-workbench-plan.md`. Ready to execute.
