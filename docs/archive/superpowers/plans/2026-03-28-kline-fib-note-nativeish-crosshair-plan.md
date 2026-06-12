# K 线 Fib / 价格标注编辑与轴联动十字光标 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add editing support for `fibonacci_retracement` and `price_note`, and make the K-line crosshair labels track chart price/time coordinates more like native axes.

**Architecture:** Keep overlay-driven interaction as the single pointer layer. Extend `KlineChart.vue` to expose a lightweight chart projector, teach `KlineDrawingOverlay.vue` to consume that projector for crosshair and price-note label editing, and expand `klineOverlayGeometry.ts` for fib/price-note move math and projection fallback.

**Tech Stack:** Vue 3, TypeScript, Pinia, Vitest, lightweight-charts

---

## Chunk 1: Lock The New Contract With Failing Tests

### Task 1: Expand geometry tests for fib / price note movement and projector-aware crosshair

**Files:**
- Modify: `frontend/src/utils/klineOverlayGeometry.test.ts`

- [ ] **Step 1: Write the failing test**

Add assertions for:
- moving `fibonacci_retracement` preserves both anchors with `timeDelta + priceDelta`
- moving `price_note` updates its single anchor to the target slot
- crosshair projection preferring projector-provided x/y/price/time values over fallback math

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts`
Expected: FAIL because the helper does not yet support the new tool cases / projector path.

### Task 2: Expand overlay tests for fib editing, price-note editing, and axis-linked crosshair

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- selected fib rendering anchor handles and emitting anchor/body commit events
- selected price note rendering an anchor handle and emitting move commit
- double-clicking or keyboard-triggering price-note label edit and committing `drawing-label-commit`
- crosshair labels using a passed chart-projector payload

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: FAIL because overlay still treats fib/price-note as read-only for editing and does not support label-edit commit or projector-aware crosshair.

### Task 3: Expand chart integration test for label commit and projector plumbing

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: Write the failing test**

Add assertions for:
- overlay `drawing-label-commit` calling store `commitLabelEdit`
- chart projector props being passed to the overlay stub
- hover / selected edit state clearing when symbol changes

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: FAIL because chart does not yet wire the new event / projector contract.

## Chunk 2: Implement The Minimal Production Changes

### Task 4: Extend geometry helpers

**Files:**
- Modify: `frontend/src/utils/klineOverlayGeometry.ts`

- [ ] **Step 1: Implement the minimal helper changes**

Implement:
- projector-aware crosshair projection input
- `fibonacci_retracement` move behavior matching trend-line delta semantics
- `price_note` move behavior with single-anchor update
- small helper paths needed by overlay label fallback

- [ ] **Step 2: Re-run the geometry test**

Run: `npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts`
Expected: PASS.

### Task 5: Implement overlay fib / price-note editing and projector-aware crosshair

**Files:**
- Modify: `frontend/src/components/watchlist/KlineDrawingOverlay.vue`

- [ ] **Step 1: Implement the minimal overlay changes**

Implement:
- chart projector prop consumption
- fib included in editable drawing set
- price-note anchor/body drag support
- in-overlay label edit input for `price_note`
- `drawing-label-commit` emission
- crosshair label rendering from projector output with fallback

- [ ] **Step 2: Re-run the overlay test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineDrawingOverlay.test.ts`
Expected: PASS.

### Task 6: Wire chart integration

**Files:**
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: Implement the minimal chart changes**

Implement:
- projector object passed into overlay
- `drawing-label-commit` routed to `commitLabelEdit`
- symbol/candle changes clearing hover/edit state

- [ ] **Step 2: Re-run the chart test**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/KlineChart.test.ts`
Expected: PASS.

## Chunk 3: Verification, Logging, And Delivery

### Task 7: Verify, log, and finish the branch

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log immediately after this modification unit**

Append one new top entry covering:
- fib / price-note editing
- axis-linked crosshair projection
- touched files
- verification commands actually run

- [ ] **Step 2: Run focused regressions**

Run: `npm --prefix frontend run test -- --run src/utils/klineOverlayGeometry.test.ts src/components/watchlist/KlineDrawingOverlay.test.ts src/components/watchlist/KlineChart.test.ts src/components/watchlist/KlineToolbar.test.ts src/components/watchlist/KlineIndicatorWorkbench.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
Expected: PASS.

- [ ] **Step 3: Run front-end build**

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 4: Re-check working tree**

Run: `git status --short`
Expected: only intended files are modified.

- [ ] **Step 5: Commit and merge locally**

Run non-interactive git commands to:
- commit the work with a focused message
- keep `main` as the final local branch state per user instruction
