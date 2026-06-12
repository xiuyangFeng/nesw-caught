# Manual Refresh Result Visibility Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the result of the last manual market refresh directly on the watchlist page.

**Architecture:** Store the last successful manual refresh result in `watchlistStore` and render a compact summary in the existing market-worker status panel.

**Tech Stack:** Vue 3, Pinia, existing watchlist tests, Vite build

---

## Chunk 1: TDD For Store And View

### Task 1: Add failing tests for refresh-result visibility

**Files:**
- Modify: `frontend/src/stores/watchlistStore.test.ts`
- Modify: `frontend/src/views/WatchlistView.test.ts`

- [ ] **Step 1: Write failing tests**

Cover:
- `refreshMarketQuotes()` stores the last successful refresh result
- `WatchlistView` renders the refresh result summary

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`
Expected: FAIL because no refresh result state is shown yet.

- [ ] **Step 3: Implement minimal store and view updates**

Add a `lastManualRefreshResult` state field and render it in the market-worker panel.

- [ ] **Step 4: Re-run focused tests**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`
Expected: PASS.

## Chunk 2: Verification And Delivery

### Task 2: Update change log and verify

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update code change log**

Record the manual refresh result visibility change.

- [ ] **Step 2: Run focused verification**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`
Expected: PASS.

- [ ] **Step 3: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS.
