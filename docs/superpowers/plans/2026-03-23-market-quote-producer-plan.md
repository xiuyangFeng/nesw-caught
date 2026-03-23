# Market Quote Producer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace request-triggered watchlist quote refreshes with a background market quote producer while keeping the existing event contract and API shape stable.

**Architecture:** Add a lifecycle-managed background producer that polls watchlist symbols, writes snapshots, and publishes `market.watchlist_refreshed`. Move market routes to cached reads so HTTP becomes a consumer of produced data instead of the producer itself.

**Tech Stack:** FastAPI lifespan hooks, SQLAlchemy sessions, existing quote provider abstraction, hybrid event bus, pytest

---

## Chunk 1: Producer Domain And Cached Read API

### Task 1: Add failing tests for background producer behavior

**Files:**
- Create: `backend/tests/test_market_quote_producer.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/quote_service.py`
- Create: `backend/app/services/market_quote_producer.py`

- [ ] **Step 1: Write the failing producer tests**

Add tests covering:
- producer runs one cycle and publishes `market.watchlist_refreshed`
- producer skips publish when watchlist is empty
- producer logs and survives refresh exceptions

- [ ] **Step 2: Run producer tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_market_quote_producer.py -q`
Expected: FAIL because `MarketQuoteProducer` does not exist yet.

- [ ] **Step 3: Write minimal producer implementation**

Add a small producer service that:
- accepts a quote service factory, session factory, event bus, logger, and poll interval
- exposes `run_cycle()`, `start()`, and `stop()`
- opens a fresh session per cycle
- refreshes watchlist quotes and publishes the event payload

- [ ] **Step 4: Re-run producer tests**

Run: `conda run -n news-caught pytest backend/tests/test_market_quote_producer.py -q`
Expected: PASS.

### Task 2: Add failing tests for cached market routes

**Files:**
- Modify: `backend/tests/test_market.py`
- Modify: `backend/app/api/routes/market.py`
- Modify: `backend/app/services/quote_service.py`

- [ ] **Step 1: Write failing route tests**

Add tests covering:
- `/api/market/watchlist` uses cached-read service method and does not publish refresh events
- `/api/market/symbols/{symbol}` uses cached-read service method
- missing cache returns structured unavailable payload without direct provider fetch

- [ ] **Step 2: Run route tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: FAIL because routes still call refresh-style methods and publish refresh events directly.

- [ ] **Step 3: Implement minimal cached-read service and route changes**

Update `QuoteService` to separate:
- `refresh_watchlist_quotes(session)`
- `get_cached_watchlist_quotes(session)`
- `get_cached_symbol_quote(symbol, session)`

Update market routes to use only cached-read methods.

- [ ] **Step 4: Re-run route tests**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS.

## Chunk 2: Lifecycle Wiring And Configuration

### Task 3: Add failing lifecycle/config tests

**Files:**
- Modify: `backend/tests/test_event_bus.py`
- Modify: `backend/tests/test_stream_status.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests for config and lifespan wiring**

Cover:
- settings expose producer interval and enable flag
- app startup constructs and starts the market producer
- app shutdown stops the market producer

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_event_bus.py backend/tests/test_stream_status.py backend/tests/test_market_quote_producer.py -q`
Expected: FAIL because producer config and lifecycle wiring are missing.

- [ ] **Step 3: Implement lifecycle wiring**

Add settings fields, initialize the producer in app startup, and stop it in shutdown. Keep existing event-bus subscriber registration intact.

- [ ] **Step 4: Re-run focused tests**

Run: `conda run -n news-caught pytest backend/tests/test_event_bus.py backend/tests/test_stream_status.py backend/tests/test_market_quote_producer.py -q`
Expected: PASS.

## Chunk 3: Documentation And Regression Verification

### Task 4: Update docs and verification records

**Files:**
- Modify: `README.md`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update README**

Document that:
- watchlist quotes are now produced by a background polling task
- market routes return cached/latest produced quotes
- new environment variables control the producer

- [ ] **Step 2: Update code change log**

Add a top entry describing the producer migration, touched files, API/event compatibility, verification, and follow-up risks.

- [ ] **Step 3: Run final regression verification**

Run: `conda run -n news-caught pytest backend/tests/test_market_quote_producer.py backend/tests/test_market.py backend/tests/test_event_bus.py backend/tests/test_stream_status.py -q`
Expected: PASS.

- [ ] **Step 4: Run full backend verification**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS.

- [ ] **Step 5: Re-read the design and check requirements**

Confirm line-by-line that the implementation:
- moves quote production off the request path
- keeps `market.watchlist_refreshed`
- preserves route response structure
- documents new runtime controls
