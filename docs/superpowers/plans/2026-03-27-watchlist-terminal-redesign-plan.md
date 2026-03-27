# Watchlist Terminal Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the watchlist list/detail UI into a denser trading-terminal layout with compact cards, a larger K-line chart, and a right-side technical dashboard.

**Architecture:** Keep the current route/store/API structure intact. Concentrate the redesign in `StockCard`, `StockDetailPanel`, and `KlineChart`, deriving advanced dashboard metrics from existing quote and candle data instead of adding backend fields.

**Tech Stack:** Vue 3, Pinia, Vitest, lightweight-charts, Tailwind utility classes

---

### Task 1: Lock regression tests for compact detail layout

**Files:**
- Modify: `frontend/src/components/watchlist/StockDetailPanel.test.ts`
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`

- [ ] **Step 1: Write failing tests**

Add assertions for:
- compact quote header / right metrics matrix
- right-side dashboard panel
- sub-indicator switch buttons (`VOL`, `MACD`, `KDJ`)

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts`
Expected: FAIL because the new terminal layout does not exist yet.

- [ ] **Step 3: Implement minimal UI changes**

Update the components to satisfy the new structure without changing route/store contracts.

- [ ] **Step 4: Run tests to verify they pass**

Run the same Vitest command and confirm PASS.

### Task 2: Compact the watchlist list cards

**Files:**
- Modify: `frontend/src/components/watchlist/StockCard.vue`

- [ ] **Step 1: Implement denser card layout**

Move status/market/change metrics into a tighter right-side stack, reduce vertical padding, and keep select/delete behavior unchanged.

- [ ] **Step 2: Run targeted verification**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: PASS.

### Task 3: Build the terminal-style detail page

**Files:**
- Modify: `frontend/src/components/watchlist/StockDetailPanel.vue`
- Modify: `frontend/src/components/watchlist/KlineChart.vue`
- Modify: `frontend/src/views/WatchlistDetailView.test.ts` if layout assertions need updates

- [ ] **Step 1: Implement compact quote header and indicator matrix**

Show the name/price block on the left and dense quote-derived metrics on the right.

- [ ] **Step 2: Implement larger chart area plus right-side dashboard**

Add the wider chart shell, technical dashboard, and instrument-style readouts derived from current props.

- [ ] **Step 3: Implement sub-indicator switch**

Support `VOL`, `MACD`, and `KDJ` views in the lower panel while keeping existing news event chips.

- [ ] **Step 4: Run focused tests**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts src/views/WatchlistDetailView.test.ts`
Expected: PASS.

### Task 4: Final verification and documentation

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run combined frontend verification**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts`
Expected: PASS.

- [ ] **Step 2: Run production build**

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 3: Update change log**

Append a top entry describing the compact terminal redesign, affected files, validation, and residual risks.
