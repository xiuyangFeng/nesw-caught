# K 线图专业终端化优化 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the watchlist K-line panel into a more professional, chart-first terminal layout with an in-chart HUD and denser supporting controls.

**Architecture:** Keep the current `KlineChart` composition and store model intact. Use `KlineChart.vue` as the main integration point for a new chart-stage layout and hover-readout state, with supporting UI refinements in `KlineToolbar.vue`, `KlineIndicatorWorkbench.vue`, and `KlineDrawingOverlay.vue`.

**Tech Stack:** Vue 3, TypeScript, Pinia, Vitest, lightweight-charts, Tailwind utility classes

---

## Chunk 1: Define The New Chart-First UI Through Tests

### Task 1: Lock the new K-line chart structure with failing tests

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: Write the failing test**

Add assertions for:
- a new in-chart HUD container showing latest candle readouts by default
- the HUD switching to a hovered candle after the overlay emits a hover payload
- summary and legend moving into the chart stage instead of a separate summary card
- the right workbench still being collapsible while the main chart expands
- a denser sub-indicator control strip and latest-readout section remaining visible

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: FAIL because the current DOM structure still uses the old summary card and has no HUD.

### Task 2: Lock the denser control surfaces with failing component tests

**Files:**
- Create: `frontend/src/components/watchlist/KlineToolbar.test.ts`
- Create: `frontend/src/components/watchlist/KlineIndicatorWorkbench.test.ts`

- [ ] **Step 1: Write the failing tests**

Add assertions for:
- toolbar being rendered as a terminal-style control strip with grouped sections
- workbench surfacing active template summary and template cards in a denser layout
- control labels needed by the new professional layout remaining accessible

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts`
Expected: FAIL because the current component markup does not match the new layout hooks.

### Task 3: Lock hover-readout integration with an overlay test

**Files:**
- Create: `frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`

- [ ] **Step 1: Write the failing test**

Add a test for:
- `mousemove` emitting `hover-anchor-change` with a `KlineDrawingAnchor` payload
- `mouseleave` emitting `hover-anchor-change` with `null`
- hover emission still working in `select` mode so the chart HUD is not blocked by the current select-path short circuit

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: FAIL because the overlay does not yet emit hover readout information.

## Chunk 2: Implement The Professional Chart Layout

### Task 4: Implement the main chart-stage layout and HUD

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`

- [ ] **Step 1: Implement the minimal chart HUD and chart-stage structure**

Implement:
- hover-candle state with fallback to latest candle
- in-chart HUD for `开 / 高 / 低 / 收 / 涨跌 / 成交量`
- chart-stage badges for symbol / period / range / active overlays
- removal of the separate summary card in favor of in-chart information layers
- keep the sub-chart as a separate `lightweight-charts` instance while visually grouping it into the same stage

- [ ] **Step 2: Re-run the KlineChart test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: PASS.

### Task 5: Rework the toolbar into a tighter control strip

**Files:**
- Modify: `frontend/src/components/watchlist/KlineToolbar.vue`

- [ ] **Step 1: Implement the toolbar polish**

Implement:
- grouped control-strip layout
- shorter visual rhythm and clearer active states
- data-role hooks added for the grouped sections needed by tests

- [ ] **Step 2: Re-run the toolbar test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts`
Expected: PASS.

### Task 6: Rework the indicator workbench into a denser side cabinet

**Files:**
- Modify: `frontend/src/components/watchlist/KlineIndicatorWorkbench.vue`

- [ ] **Step 1: Implement the side-cabinet layout**

Implement:
- compact active-template header
- denser template list cards
- tighter action row and sub-indicator row
- data-role hooks for new sections

- [ ] **Step 2: Re-run the workbench test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineIndicatorWorkbench.test.ts`
Expected: PASS.

### Task 7: Emit hover readout data from the overlay

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.vue`

- [ ] **Step 1: Implement the minimal hover event**

Implement:
- mousemove emitting the nearest candle anchor payload through `hover-anchor-change`
- mouseleave clearing the hover state
- keep hover emission active in `select`, `drawing`, and idle states
- emit `null` when overlay is disabled or there is no candle data
- keep existing draft-update behavior intact

- [ ] **Step 2: Re-run the overlay test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: PASS.

## Chunk 3: Verify, Log, And Regressions

### Task 8: Run focused regression coverage

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run the focused front-end regression suite**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
Expected: PASS.

- [ ] **Step 2: Run the front-end build**

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 3: Update the code change log**

Append one new top entry to `docs/code-change-log.md` covering:
- chart-first professional layout upgrade
- HUD / in-chart readout layer
- component files touched
- verification commands actually run

- [ ] **Step 4: Re-check working tree**

Run: `git status --short`
Expected: only intended files are modified.
