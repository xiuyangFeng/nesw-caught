# Watchlist Search And Delete Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local-candidate stock search, one-click watchlist add, and confirmed delete actions to the watchlist page.

**Architecture:** Keep watchlist create and quote/news loading flows intact, but add a new watchlist candidate endpoint and a delete endpoint on the backend, then refactor the frontend watchlist page into a single search-add toolbar above the table. Implement each behavior with failing tests first, then minimal production code.

**Tech Stack:** FastAPI, SQLAlchemy, Python, pytest, Vue 3, Pinia, TypeScript, Vitest

---

## Chunk 1: Backend Watchlist Candidate And Delete APIs

### Task 1: Add failing backend tests for candidate lookup and delete

**Files:**
- Modify: `backend/tests/test_stock_news_search.py`
- Modify: `backend/app/api/routes/watchlist.py`
- Modify: `backend/app/repositories/watchlist_repository.py`

- [ ] **Step 1: Write the failing tests**

Add route tests that:
- call `GET /api/watchlist/candidates` and assert the payload contains known watchlist candidates with `symbol`, `display_name`, `market`
- create a watchlist item, call `DELETE /api/watchlist/{symbol}`, then assert the item is removed
- call `DELETE /api/watchlist/{symbol}` for a missing symbol and assert `404`

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_stock_news_search.py -q`
Expected: FAIL because the candidate and delete endpoints do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add a watchlist candidate source plus route response schema, expose `GET /api/watchlist/candidates`, and add repository + route support for deleting by symbol.

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_stock_news_search.py -q`
Expected: PASS

## Chunk 2: Frontend API And Store Support

### Task 2: Add failing frontend tests for candidate loading and delete state

**Files:**
- Create: `frontend/src/stores/watchlistStore.test.ts`
- Modify: `frontend/src/stores/watchlistStore.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/mock.ts`

- [ ] **Step 1: Write the failing tests**

Add store tests that:
- load watchlist candidates through the API client and store them
- delete a selected symbol and clear or reassign selection correctly
- surface delete errors without wiping the existing watchlist

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`
Expected: FAIL because candidate and delete methods are missing.

- [ ] **Step 3: Write minimal implementation**

Extend the shared API types and client for candidates/delete, seed matching mock data, and add candidate + delete state/actions to `watchlistStore`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`
Expected: PASS

## Chunk 3: Watchlist UI Search-Add Toolbar And Row Delete

### Task 3: Add failing component/view tests for search and delete interactions

**Files:**
- Create: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/components/watchlist/WatchlistTable.test.ts`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/components/watchlist/WatchlistTable.vue`

- [ ] **Step 1: Write the failing tests**

Add UI tests that:
- render the merged search-add toolbar above the table
- filter candidates from user input and show a selectable list
- mark already-added candidates as disabled
- call delete with confirmation when the delete button is pressed
- keep row click and delete click separated

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/components/watchlist/WatchlistTable.test.ts`
Expected: FAIL because the new toolbar, candidate list, and delete button do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Refactor `WatchlistView` into a single management card, wire the local candidate search UI to the store, and extend `WatchlistTable` with an actions column and delete event handling.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/components/watchlist/WatchlistTable.test.ts`
Expected: PASS

## Chunk 4: Records And Focused Verification

### Task 4: Update records and run focused verification

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log**

Add a top entry describing the watchlist search candidate flow, delete interaction, affected files, validation, and residual risks.

- [ ] **Step 2: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_stock_news_search.py -q`
Expected: PASS

- [ ] **Step 3: Run frontend verification**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts src/components/watchlist/WatchlistTable.test.ts`
Expected: PASS

- [ ] **Step 4: Run production build**

Run: `npm --prefix frontend run build`
Expected: PASS
