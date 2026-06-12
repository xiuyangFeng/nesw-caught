# A-Share Watchlist & K-Line Expansion Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing watchlist, quote, sparkline, K-line, and related-content flow so A-share symbols (`600519.SH` / `000001.SZ`) work alongside HK and US symbols.

**Architecture:** Keep the current watchlist-first market architecture, but extend symbol normalization and candidate coverage so `cn` symbols flow through the same `QuoteService`, `MarketChartService`, and frontend watchlist store used by HK/US. Persist A-share watchlist symbols only in canonical `.SH/.SZ` form, while translating Shanghai provider access from `.SH` to Yahoo's `.SS`. Reuse existing `cn` news sources and related-news lookup so A-share K-line markers come from the same backend path instead of adding a new content subsystem.

**Tech Stack:** FastAPI, SQLAlchemy, pandas/yfinance, Vue 3, Pinia, Vitest, pytest

---

## Chunk 1: Backend A-share symbol support

### Task 1: Lock A-share symbol normalization and quote detail behavior

**Files:**
- Modify: `backend/app/services/quote_provider.py`
- Modify: `backend/app/api/routes/watchlist.py`
- Modify: `backend/app/repositories/watchlist_repository.py` only if repository helpers need canonical lookup
- Modify: `backend/tests/test_market.py`
- Modify: `backend/tests/test_stock_news_search.py`

- [ ] **Step 1: Write the failing backend tests**

Add tests in `backend/tests/test_market.py` for:
- `normalize_symbol()` accepting `600519.SH`, `000001.SZ`, `SH600519`, `SZ000001`
- `normalize_symbol()` accepting six-digit input when `market="cn"`
- Shanghai symbols translating canonical `.SH` into provider `.SS`
- market detail route preserving the caller symbol while returning the translated provider symbol

Add tests in `backend/tests/test_stock_news_search.py` for:
- `POST /api/watchlist` canonicalizing A-share alias inputs before persistence
- candidate list including a concrete A-share entry

- [ ] **Step 2: Run the targeted backend tests and verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: FAIL because A-share symbol normalization is not implemented yet

- [ ] **Step 3: Implement minimal normalization changes**

Update `backend/app/services/quote_provider.py` so:
- canonical `.SH/.SZ` input round-trips as `market="cn"`
- `SHxxxxxx` / `SZxxxxxx` normalize to `.SH/.SZ`
- six-digit input with `market="cn"` maps by prefix (`6` => `.SH`, `0/3` => `.SZ`)
- Shanghai provider symbols translate from canonical `.SH` to provider `.SS`
- unsupported CN formats still raise `ValueError`

Update `backend/app/api/routes/watchlist.py` so A-share aliases are canonicalized before duplicate check and persistence.

- [ ] **Step 4: Re-run the backend tests**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS for the new normalization coverage

### Task 2: Lock A-share kline/sparkline behavior

**Files:**
- Modify: `backend/app/services/market_chart_service.py`
- Modify: `backend/tests/test_market.py`

- [ ] **Step 1: Write failing tests for A-share kline and sparkline**

Add tests in `backend/tests/test_market.py` for:
- A-share watchlist symbols can return K-line data
- sparkline requests include A-share symbols when history exists
- related news aligned to an A-share watchlist symbol still becomes `news_events`

- [ ] **Step 2: Run the backend tests and verify failure**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: FAIL because `cn` symbols are still blocked in the quote/chart path

- [ ] **Step 3: Implement the minimal backend code**

Use the new symbol normalization in existing services. Keep:
- watchlist membership checks unchanged
- `provider_symbol` equal to canonical `.SH/.SZ`
- K-line/news-event shaping unchanged except now it works for `cn`

- [ ] **Step 4: Re-run the backend tests**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS

## Chunk 2: Candidate pool and watchlist creation

### Task 3: Add A-share default candidates

**Files:**
- Modify: `backend/app/services/watchlist_candidates.py`
- Modify: `backend/tests/test_stock_news_search.py`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/views/WatchlistView.test.ts`

- [ ] **Step 1: Write the failing candidate test**

Add or extend backend/frontend coverage so the candidate list includes concrete A-share entries with:
- `market="cn"`
- canonical `.SH/.SZ` symbols
- aliases including Chinese name and raw six-digit code
- fallback/mock data matching the real candidate list shape

- [ ] **Step 2: Run the focused test and verify it fails**

Run:
- `conda run -n news-caught pytest backend/tests/test_stock_news_search.py -q`
- `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: FAIL because no A-share candidates exist yet

- [ ] **Step 3: Add a minimal A-share candidate set**

Extend `WATCHLIST_CANDIDATES` and `frontend/src/api/mock.ts` with the agreed concrete A-share set. Keep ordering intentional so the add modal and degraded mode expose the same symbols.

- [ ] **Step 4: Re-run the focused tests**

Expected: PASS

## Chunk 3: Frontend watchlist/store coverage

### Task 4: Lock A-share watchlist and K-line store behavior

**Files:**
- Modify: `frontend/src/stores/watchlistStore.test.ts`
- Modify: `frontend/src/stores/watchlistStore.ts`
- Modify: `frontend/src/types/api.ts` only if new fixtures require stronger typing
- Modify: `frontend/src/views/WatchlistView.test.ts` if add-flow coverage needs store fixture updates

- [ ] **Step 1: Write the failing frontend store tests**

Add tests for:
- loading watchlist candidates that include `cn`
- creating/selecting an A-share symbol and then loading K-line + related news
- preserving canonical symbol labels through the store state
- add modal flow continuing to work when the selected candidate is A-share

- [ ] **Step 2: Run the store test file and verify failure**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`
Expected: FAIL because the test fixtures/assertions describe A-share behavior not yet covered

- [ ] **Step 3: Implement the minimal frontend changes**

Keep the existing watchlist store flow. Only adjust code if tests prove a gap around:
- candidate handling
- selected symbol flow
- symbol rendering assumptions for `.SH/.SZ`

- [ ] **Step 4: Re-run the store tests**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`
Expected: PASS

### Task 5: Lock A-share rendering in watchlist detail components

**Files:**
- Modify: `frontend/src/components/watchlist/StockDetailPanel.test.ts`
- Modify: `frontend/src/components/watchlist/KlineChart.test.ts`
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/components/watchlist/WatchlistAddModal.vue` only if behavior changes are required by tests

- [ ] **Step 1: Write failing component tests**

Add tests for:
- A-share symbol labels rendering in the detail panel
- A-share K-line payloads still rendering markers/tooltips with existing behavior
- watchlist page add flow accepting an A-share candidate end-to-end

- [ ] **Step 2: Run the targeted frontend tests and verify failure**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts`
Run also: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: FAIL if component/view assumptions do not yet cover A-share fixtures

- [ ] **Step 3: Implement only the fixes required to make the tests pass**

Avoid introducing A-share-specific UI branches unless the tests expose a real formatting gap.

- [ ] **Step 4: Re-run the targeted tests**

Expected: PASS

## Chunk 4: Wrap-up and verification

### Task 6: Update records and verify end-to-end

**Files:**
- Modify: `docs/code-change-log.md`
- Modify: `docs/superpowers/specs/2026-03-30-a-share-watchlist-kline-design.md` only if implementation forces a spec correction
- Modify: `docs/superpowers/plans/2026-03-30-a-share-watchlist-kline-plan.md` only if implementation forces a plan correction

- [ ] **Step 1: Append a change-log entry**

Record:
- A-share symbol normalization
- watchlist candidate expansion
- A-share quote/K-line/sparkline enablement
- verification commands and residual risks

- [ ] **Step 2: Run fresh verification commands**

Run:
- `conda run -n news-caught pytest backend/tests/test_market.py -q`
- `conda run -n news-caught pytest backend/tests/test_stock_news_search.py -q`
- `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/components/watchlist/StockDetailPanel.test.ts src/components/watchlist/KlineChart.test.ts src/views/WatchlistView.test.ts`
- `npm --prefix frontend run build`

Expected: all commands exit `0`

- [ ] **Step 3: Request review and fix findings before merge**

Run the required review workflow against the final diff, address material issues, then proceed to push and merge.
