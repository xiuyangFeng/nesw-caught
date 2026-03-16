# Watchlist Real Market Data Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real quote fetching for Hong Kong and US watchlist symbols, a richer watchlist overview, and a dedicated stock detail page.

**Architecture:** Extend the backend with a normalized quote service and provider abstraction backed by cached snapshots, then move the frontend from client-side snapshot joins to watchlist-specific quote endpoints and a new stock detail route. Keep provider boundaries explicit so the project can later switch from a free source to key-based or paid providers.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, Pydantic, pytest, Vue 3, Pinia, Vue Router, TypeScript, yfinance

---

## Chunk 1: Backend Quote Domain

### Task 1: Add failing backend tests for symbol normalization and quote APIs

**Files:**
- Modify: `backend/tests/test_watchlist.py`
- Modify: `backend/tests/test_market.py`

- [ ] **Step 1: Write failing symbol normalization tests**

Add tests that assert:
- `HK253` normalizes to `0253.HK`
- `0700.HK` stays provider-compatible
- `AAPL` stays unchanged

- [ ] **Step 2: Run normalization tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -k normalize -q`
Expected: FAIL because normalization code does not exist yet

- [ ] **Step 3: Write failing watchlist quote API tests**

Add tests for:
- `GET /api/market/watchlist` returns expanded quote fields
- Partial provider failure still returns records for all watchlist items with status values
- `GET /api/market/symbols/{symbol}` returns detailed quote payload

- [ ] **Step 4: Run quote API tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: FAIL because endpoints and response schema do not exist yet

### Task 2: Implement backend quote models, provider abstraction, and market endpoints

**Files:**
- Modify: `backend/app/models/price_snapshot.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/db/initializer.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/repositories/market_repository.py`
- Modify: `backend/app/api/routes/market.py`
- Modify: `backend/app/schemas/market.py`
- Create: `backend/app/services/quote_provider.py`
- Create: `backend/app/services/quote_service.py`

- [ ] **Step 1: Add the minimal production code**

Implement:
- expanded `PriceSnapshot` cache fields
- unified quote schemas for overview and detail
- symbol normalization helpers
- provider interface and default Yahoo Finance implementation hook
- quote service for watchlist batch fetch and single-symbol detail
- new market endpoints

- [ ] **Step 2: Run backend market tests**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS

- [ ] **Step 3: Refactor only if tests stay green**

Tighten naming and helper extraction only if needed.

### Task 3: Add provider parsing and cache fallback tests

**Files:**
- Modify: `backend/tests/test_market.py`

- [ ] **Step 1: Write failing provider/caching tests**

Add tests for:
- provider payload mapping into unified quote fields
- cached snapshot fallback marks quote status as delayed
- unsupported symbol returns `symbol_not_supported`

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -k "provider or delayed or supported" -q`
Expected: FAIL for the newly added cases

- [ ] **Step 3: Implement the minimal backend changes**

Adjust provider mapping and cache fallback behavior until the new tests pass.

- [ ] **Step 4: Re-run backend market tests**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS

## Chunk 2: Frontend Watchlist Overview

### Task 4: Add failing frontend typing and mock support for expanded watchlist quote data

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Write the failing type and client changes**

Add new types and API client methods for:
- watchlist overview quotes
- stock detail quote

Keep TypeScript references intentionally incomplete so the build fails first.

- [ ] **Step 2: Run frontend build to verify failure**

Run: `npm --prefix frontend run build`
Expected: FAIL because new types and client usage are incomplete

- [ ] **Step 3: Implement minimal type-safe client support**

Add complete type definitions, client methods, and mock fallbacks.

- [ ] **Step 4: Re-run frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS or fail only on next missing UI task

### Task 5: Replace client-side snapshot joins with quote overview data

**Files:**
- Modify: `frontend/src/stores/watchlistStore.ts`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/components/watchlist/WatchlistTable.vue`

- [ ] **Step 1: Add failing UI references to expanded quote fields**

Update the watchlist overview UI to reference:
- latest price
- change amount
- change percent
- open
- previous close
- high
- low
- volume
- status

- [ ] **Step 2: Run frontend build to verify failure**

Run: `npm --prefix frontend run build`
Expected: FAIL because store data flow is not complete yet

- [ ] **Step 3: Implement minimal overview store and table changes**

Wire the watchlist page to:
- fetch watchlist overview quotes from backend
- render status-aware values
- keep add-watchlist flow working

- [ ] **Step 4: Re-run frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS or fail only on missing detail-route work

## Chunk 3: Frontend Stock Detail Route

### Task 6: Add failing route and stock detail view integration

**Files:**
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/views/WatchlistDetailView.vue`
- Modify: `frontend/src/stores/watchlistStore.ts`

- [ ] **Step 1: Add a failing detail route and view reference**

Create a route for `/watchlist/:symbol` and reference a detail view that expects detail quote data.

- [ ] **Step 2: Run frontend build to verify failure**

Run: `npm --prefix frontend run build`
Expected: FAIL because detail data loading and view implementation are incomplete

- [ ] **Step 3: Implement minimal detail page support**

Add:
- detail quote fetch method
- detail page layout
- related news reuse
- row click navigation from watchlist overview

- [ ] **Step 4: Re-run frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS

## Chunk 4: Integration and Verification

### Task 7: Add dependency/config support and run full verification

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `requirements.txt`
- Modify: `README.md`
- Modify: `docs/api-contract.md`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Write failing integration expectations where needed**

Add or update documentation references to the new quote provider dependency and API contracts.

- [ ] **Step 2: Implement the minimal dependency and doc updates**

Document:
- provider choice
- config knobs
- new endpoints
- watchlist detail route behavior

- [ ] **Step 3: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS

- [ ] **Step 4: Run frontend verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 5: Perform manual spot checks**

Verify at least:
- `0700.HK`
- `HK253`
- `AAPL`

- [ ] **Step 6: Commit**

```bash
git add backend frontend README.md requirements.txt docs/api-contract.md docs/code-change-log.md
git commit -m "实现自选股真实行情与详情页"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-16-watchlist-real-market-data-plan.md`. Ready to execute?
