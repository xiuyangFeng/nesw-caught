# Manual Market Refresh Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual one-shot market refresh action for operators, exposed via backend API and watchlist UI.

**Architecture:** Keep the independent market worker as the default producer, but add a dedicated `POST /api/market/refresh` operator endpoint that performs a one-shot quote refresh and publishes the usual event. Surface the action in the watchlist UI and reload relevant state after success.

**Tech Stack:** FastAPI routes, QuoteService, event bus, Vue 3, Pinia, Vitest, pytest

---

## Chunk 1: Backend TDD

### Task 1: Add failing tests for manual market refresh API

**Files:**
- Modify: `backend/tests/test_market.py`
- Modify: `backend/app/api/routes/market.py`
- Modify: `backend/app/schemas/market.py`

- [ ] **Step 1: Write failing tests**

Cover:
- `POST /api/market/refresh` returns a refresh summary
- route publishes `market.watchlist_refreshed`

- [ ] **Step 2: Run focused backend tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: FAIL because the route does not exist.

- [ ] **Step 3: Implement minimal backend endpoint**

Add the route and summary schema, reuse `QuoteService.refresh_watchlist_quotes()` and event publication.

- [ ] **Step 4: Re-run backend tests**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS.

## Chunk 2: Frontend TDD

### Task 2: Add failing tests for manual refresh UI

**Files:**
- Modify: `frontend/src/stores/watchlistStore.test.ts`
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/stores/watchlistStore.ts`
- Modify: `frontend/src/views/WatchlistView.vue`

- [ ] **Step 1: Write failing frontend tests**

Cover:
- store exposes `refreshMarketQuotes()`
- action calls backend refresh endpoint, then reloads watchlist data
- WatchlistView renders the refresh button and disables it while running

- [ ] **Step 2: Run focused frontend tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`
Expected: FAIL because no manual refresh action exists.

- [ ] **Step 3: Implement minimal frontend wiring**

Add client method, store action/state, and button UI.

- [ ] **Step 4: Re-run frontend tests**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`
Expected: PASS.

## Chunk 3: Verification

### Task 3: Update change log and verify

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update code change log**

Record the manual operator refresh capability.

- [ ] **Step 2: Run targeted verification**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS.

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`
Expected: PASS.

- [ ] **Step 3: Run build/full verification**

Run: `npm --prefix frontend run build`
Expected: PASS.

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS.
