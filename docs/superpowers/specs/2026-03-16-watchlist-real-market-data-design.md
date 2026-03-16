# Watchlist Real Market Data Design

## Background

The current watchlist page joins `/api/watchlist` and `/api/market/snapshots` on the frontend. Newly added symbols such as `HK253` show `--` when the backend has no matching snapshot row. The current interaction also keeps stock-specific news inside the watchlist page, so users cannot drill into a dedicated stock detail view with richer quote fields.

This design changes the watchlist flow from seed snapshot display to real quote retrieval for Hong Kong and US equities, with free data providers first and provider abstraction kept for future paid upgrades.

## Goals

- Show real quote data for watchlist symbols in Hong Kong and US markets.
- Support both `0700.HK`-style and `HK253`-style user input for Hong Kong symbols.
- Add a watchlist overview page that displays key metrics for all watchlist symbols in one place.
- Add a dedicated stock detail page that shows richer quote metrics and related news for a single symbol.
- Keep the provider layer replaceable so the project can later switch to key-based or paid providers without rewriting frontend pages.

## Non-Goals

- No A-share market support in this change.
- No intraday charting or K-line rendering in this change.
- No automated background scheduler for quote refresh in this change.
- No commitment to exchange-grade real-time SLA while using free providers.

## User Experience

### Watchlist Overview

The watchlist page remains the batch overview entry. Each row shows:

- Display name
- Symbol
- Market
- Latest price
- Daily change amount
- Daily change percent
- Open
- Previous close
- Day high
- Day low
- Volume
- Updated time
- Data status

Clicking a row navigates to a dedicated stock detail page.

Rows with unavailable quote data still render, but show a status such as `unavailable` or `fetch_failed` instead of silently leaving only `--`.

### Stock Detail Page

Route shape: `/watchlist/:symbol`

The detail page contains:

- Core quote card: latest price, change amount, change percent
- Metrics card: open, previous close, high, low, volume
- Metadata card: display name, symbol, market, provider name, quote status, latest update time
- Related news section: reusing the existing stock-related news query

## Architecture

### Symbol Normalization

Add a normalization layer before provider fetches.

Responsibilities:

- Normalize user input symbol casing
- Convert supported Hong Kong aliases such as `HK253` to provider-friendly codes such as `0253.HK`
- Preserve already normalized symbols such as `0700.HK` and US symbols such as `AAPL`
- Return a machine-readable error when the symbol cannot be normalized

The watchlist database may continue storing the user-facing symbol, but quote fetches should use a normalized provider symbol plus a canonical display symbol in responses.

### Quote Provider Abstraction

Introduce a quote provider interface with a unified output model.

Provider responsibilities:

- Fetch a quote for one normalized symbol
- Optionally fetch quotes in batch
- Map provider-specific payloads to a unified quote model

First implementation:

- `YahooFinanceQuoteProvider` using `yfinance` as the free default source

Future implementations:

- `AlphaVantageQuoteProvider`
- `TwelveDataQuoteProvider`

Provider selection should be config-driven so future migration does not require API contract changes.

### Quote Service

Add a service layer above providers.

Responsibilities:

- Resolve watchlist items to normalized symbols
- Fetch quotes in batch for watchlist overview
- Fetch a single detailed quote for stock detail page
- Apply short TTL caching
- Fall back to the latest cached successful quote when upstream fetch fails
- Return per-symbol status and source metadata

Suggested cache window:

- 1 to 3 minutes TTL for successful quotes

### Persistence

Keep using the existing `price_snapshot` table, but expand its role from seed-only snapshots to quote cache storage.

Recommended additions:

- Store open price
- Store previous close
- Store day high
- Store day low
- Store provider name
- Store quote status
- Store optional provider symbol
- Store optional status message

The table becomes the short-term cache and the source for fallback responses when the live provider fails.

## API Design

### `GET /api/market/watchlist`

Returns one summary record per watchlist symbol with:

- `symbol`
- `display_name`
- `market`
- `provider_symbol`
- `price`
- `change_amount`
- `change_percent`
- `open_price`
- `previous_close`
- `day_high`
- `day_low`
- `volume`
- `status`
- `source`
- `message`
- `fetched_at`

Behavior:

- Uses live provider fetch with cache support
- Partial failure allowed; failed symbols still return records with status fields

### `GET /api/market/symbols/{symbol}`

Returns detailed quote data for a single symbol with the same fields as overview plus:

- `is_abnormal`
- `abnormal_reason`

Behavior:

- Normalizes the route symbol first
- Returns a structured status when the symbol is unsupported or fetch fails

### Existing APIs

- `/api/watchlist` stays focused on watchlist membership and user-entered metadata
- `/api/watchlist/{symbol}/related-news` remains available and is consumed by the stock detail page
- `/api/market/snapshots` can be kept as a compatibility endpoint initially, but the new frontend pages should move to the new watchlist-oriented quote API

## Frontend Design

### Watchlist Overview Page

Update the current watchlist page to consume `GET /api/market/watchlist` instead of joining snapshots in the client.

Changes:

- Show the expanded quote columns
- Keep the add-watchlist form
- Change row click behavior from inline related-news selection to route navigation
- Replace silent blanks with explicit status text where needed

### Stock Detail Page

Add a new view and route for `/watchlist/:symbol`.

The page should:

- Fetch detailed quote data on load
- Fetch related news for the symbol
- Show loading, unavailable, and fetch-failed states clearly
- Reuse existing card and loading components where appropriate

## Error Handling

Each quote response should expose a machine-readable status:

- `ok`
- `delayed`
- `unavailable`
- `symbol_not_supported`
- `fetch_failed`

Rules:

- One symbol failing must not fail the full watchlist overview response
- Fallback cached quotes should be marked `delayed`
- Unsupported symbols should include a clear message
- Frontend should display status text instead of only `--`

## Testing Strategy

### Backend

- Symbol normalization tests for `HK253`, `0700.HK`, `AAPL`
- Provider mapping tests from raw provider payload to unified quote model
- Watchlist quote API tests with mixed success and failure responses
- Single-symbol detail API tests for success and unsupported symbol cases
- Repository tests for expanded `price_snapshot` cache behavior if model changes require them

### Frontend

- Overview page renders expanded quote fields
- Overview row click navigates to the detail route
- Detail page renders quote cards plus related news
- Detail page renders `ok`, `unavailable`, and `fetch_failed` states correctly
- Build verification with `npm --prefix frontend run build`

### End-to-End Verification

- `conda run -n news-caught pytest backend/tests`
- `npm --prefix frontend run build`
- Manual verification using at least `0700.HK`, `HK253`, and `AAPL`

## Risks

- Free providers may return delayed data or change response structure without notice.
- Hong Kong symbol alias handling may require ongoing normalization updates if users enter multiple non-standard formats.
- Batch quote throughput may need tuning if the watchlist grows significantly.

## Open Decisions Resolved In This Spec

- Markets in scope: Hong Kong and US only
- Provider preference: free source first, with future paid-provider expansion preserved
- Primary UX: dedicated stock detail page plus batch overview page
