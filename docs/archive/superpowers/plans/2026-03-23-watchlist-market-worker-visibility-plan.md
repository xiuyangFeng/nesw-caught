# Watchlist Market Worker Visibility Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the independent market worker runtime status directly on the watchlist page.

**Architecture:** Extend the frontend stream-status typing, let `watchlistStore` fetch and retain only the `market_worker` portion during watchlist loads, and render a compact status panel in `WatchlistView`.

**Tech Stack:** Vue 3 Composition API, Pinia, existing API client, Vitest, Vite build

---

## Chunk 1: TDD For Store And View

### Task 1: Add failing tests for market-worker status loading

**Files:**
- Modify: `frontend/src/stores/watchlistStore.test.ts`
- Modify: `frontend/src/views/WatchlistView.test.ts`

- [ ] **Step 1: Write failing tests**

Cover:
- `watchlistStore.loadWatchlist()` calls `getStreamStatus()` and stores `market_worker`
- `WatchlistView` renders the worker status and last error

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`
Expected: FAIL because the store and view do not yet expose market-worker state.

- [ ] **Step 3: Implement minimal store/view changes**

Add the smallest state and template changes needed to satisfy the tests.

- [ ] **Step 4: Re-run focused tests**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`
Expected: PASS.

## Chunk 2: Typing And Documentation

### Task 2: Update API typing and docs

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update stream status types**

Model the backend `market_worker` payload explicitly.

- [ ] **Step 2: Update change log**

Record the watchlist-visible worker status change and verification.

- [ ] **Step 3: Run focused verification**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`
Expected: PASS.

- [ ] **Step 4: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS.
