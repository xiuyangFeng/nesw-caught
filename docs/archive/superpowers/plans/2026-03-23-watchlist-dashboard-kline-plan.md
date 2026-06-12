# Watchlist Dashboard & K-Line Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current `/watchlist` management table with a master-detail trading dashboard backed by new market kline and sparkline APIs.

**Architecture:** Add a dedicated backend market chart service that validates watchlist membership, fetches/caches OHLCV data, derives technical indicators and aligned news markers, then expose it through `/api/market/symbols/{symbol}/kline` and `/api/market/sparklines`. Extend the frontend watchlist store to own selected symbol, chart state, sparklines, and detail news, then render a new dashboard view composed of focused watchlist/chart/news components while preserving the existing `/watchlist/:symbol` fallback page.

**Tech Stack:** FastAPI, SQLAlchemy, pandas/yfinance, Redis cache fallback, Vue 3, Pinia, Vitest, Lightweight Charts

---

## Chunk 1: Backend Market Chart APIs

### Task 1: Add kline/sparkline schemas and backend tests

**Files:**
- Create: `backend/app/services/market_chart_service.py`
- Modify: `backend/app/schemas/market.py`
- Modify: `backend/tests/test_market.py`
- Modify: `backend/tests/conftest.py` or adjacent backend test helpers only if new fixtures are required

- [ ] **Step 1: Write the failing backend route/service tests**

Add focused tests in `backend/tests/test_market.py` for:
- `GET /api/market/symbols/{symbol}/kline` returns candles, indicators, `news_events`, and `stale`
- non-watchlist symbol returns `404`
- stale-cache fallback returns cached payload with `stale=true`
- `POST /api/market/sparklines` returns per-symbol price arrays and rejects more than 30 symbols
- weekend/holiday news timestamps align to the nearest prior trading candle date

- [ ] **Step 2: Run backend tests to verify the new cases fail for the right reason**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: FAIL because kline/sparkline routes and schemas do not exist yet

- [ ] **Step 3: Add response schemas for chart payloads**

Implement Pydantic models in `backend/app/schemas/market.py` for:
- candle rows
- MA/MACD/KDJ/Bollinger series rows
- news marker items/groups
- `MarketKlineView`
- `MarketSparklineRequest`
- `MarketSparklineMap`

- [ ] **Step 4: Implement a dedicated chart service**

Create `backend/app/services/market_chart_service.py` to:
- validate watchlist membership
- normalize symbols through existing quote provider logic
- fetch OHLCV history from yfinance
- compute MA/MACD/KDJ/Bollinger with pandas
- map related-news dates onto prior trading days
- read/write cached payloads keyed by `{symbol}:{interval}:{range}`
- expose a lightweight sparkline fetch path for the last 30 closes

- [ ] **Step 5: Expose new market routes**

Update `backend/app/api/routes/market.py` with:
- `GET /api/market/symbols/{symbol}/kline`
- `POST /api/market/sparklines`
- request validation, watchlist checks, and stale fallback handling wired through the chart service

- [ ] **Step 6: Run backend tests until green**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS with the new route coverage green

### Task 2: Run broader backend verification for regressions

**Files:**
- Modify: `backend/app/api/routes/market.py`
- Modify: `backend/app/schemas/market.py`
- Create: `backend/app/services/market_chart_service.py`
- Test: `backend/tests/test_market.py`

- [ ] **Step 1: Run the full backend suite**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS with no regressions in existing market/watchlist/runtime behavior

- [ ] **Step 2: Refactor only if needed after green**

Keep any cleanup limited to naming, shared helpers, or duplication removal discovered while making the tests pass.

---

## Chunk 2: Frontend Data Layer

### Task 3: Extend frontend API/types/store for dashboard data

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/stores/watchlistStore.ts`
- Modify: `frontend/src/stores/watchlistStore.test.ts`

- [ ] **Step 1: Write failing store/API tests**

Add tests in `frontend/src/stores/watchlistStore.test.ts` covering:
- `selectSymbol(symbol)` resets stale detail state and loads kline + related news concurrently
- `switchPeriod(period)` maps UI periods to backend `interval/range`
- `loadWatchlist()` also requests sparklines for current watchlist symbols
- kline request failures set `klineError` without clearing the left-column list

- [ ] **Step 2: Run the store test file and confirm it fails**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`
Expected: FAIL because the dashboard state, API methods, and period mapping do not exist yet

- [ ] **Step 3: Add API and type definitions**

Implement new frontend types for:
- kline candles/indicators/news markers
- sparkline response maps
- dashboard period keys

Extend `frontend/src/api/client.ts` with:
- `getStockKline(symbol, interval, range)`
- `getWatchlistSparklines(symbols)`

- [ ] **Step 4: Expand the watchlist store**

Update `frontend/src/stores/watchlistStore.ts` to add:
- `selectedSymbol`, `currentPeriod`, `klineData`, `klineLoading`, `klineError`
- `sparklines`
- `detailNews`
- `selectSymbol`, `switchPeriod`, `loadSparklines`

Ensure `loadWatchlist()` fetches watchlist rows, quote snapshots, and sparklines; preserve manual refresh/runtime behavior already in place.

- [ ] **Step 5: Re-run store tests**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`
Expected: PASS

---

## Chunk 3: Frontend Dashboard UI

### Task 4: Add dashboard components with view-level tests

**Files:**
- Create: `frontend/src/components/watchlist/WatchlistSidebar.vue`
- Create: `frontend/src/components/watchlist/StockCard.vue`
- Create: `frontend/src/components/watchlist/StockSparkline.vue`
- Create: `frontend/src/components/watchlist/StockDetailPanel.vue`
- Create: `frontend/src/components/watchlist/KlineChart.vue`
- Create: `frontend/src/components/watchlist/IndicatorChart.vue`
- Create: `frontend/src/components/watchlist/StockMetricsGrid.vue`
- Create: `frontend/src/components/watchlist/RelatedNewsSidebar.vue`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/router/index.ts` only if route/view naming needs adjustment

- [ ] **Step 1: Write failing view/component tests**

Add tests in `frontend/src/views/WatchlistView.test.ts` for:
- `/watchlist` renders master-detail layout instead of the old table-first page shell
- clicking a stock card selects it and requests chart/news data
- period buttons call the store with the correct mapping
- indicator buttons disable when series data is absent
- news sidebar and chart marker interaction state is surfaced through the view/store contract

- [ ] **Step 2: Run the watchlist view tests to verify failure**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: FAIL because the new dashboard components and layout do not exist yet

- [ ] **Step 3: Implement the dashboard components**

Build focused components that follow the existing terminal UI language:
- sidebar with search/add, sorting, and scrollable stock cards
- stock card showing quote, abnormal state, and sparkline
- detail panel with period switcher, metrics grid, chart region, and related news
- chart wrappers that keep Lightweight Charts setup isolated from the page component

Keep v1 constraints from the spec:
- main/detail selection in the store
- chart/news hover-click contract may be driven by store/component state rather than full cross-chart synchronization
- preserve `/watchlist/:symbol` as a fallback route without removing the existing detail page

- [ ] **Step 4: Re-run targeted frontend tests**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/stores/watchlistStore.test.ts`
Expected: PASS

### Task 5: Run build-level frontend verification

**Files:**
- Modify: frontend files touched by Tasks 3-4

- [ ] **Step 1: Run the frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 2: Fix any compile/style regressions and re-run**

Only perform cleanup necessary to restore a clean build after the dashboard changes.

---

## Chunk 4: Wrap-Up

### Task 6: Update project records and final verification

**Files:**
- Modify: `docs/code-change-log.md`
- Modify: `docs/superpowers/plans/2026-03-23-watchlist-dashboard-kline-plan.md` only if plan corrections are needed during execution

- [ ] **Step 1: Append a code change log entry**

Record:
- backend kline/sparkline APIs
- frontend watchlist dashboard/store/component changes
- test/build verification actually run
- any remaining gaps or deferred parts

- [ ] **Step 2: Run final verification commands fresh**

Run:
- `conda run -n news-caught pytest backend/tests/test_market.py -q`
- `conda run -n news-caught pytest backend/tests -q`
- `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`
- `npm --prefix frontend run build`

Expected: all commands exit `0`

- [ ] **Step 3: Request code review before calling the work complete**

Use the required review workflow against the final diff and address any material findings before closing the task.
