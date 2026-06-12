# Market Quote Worker Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the market quote producer from the FastAPI app lifecycle into an independent worker process while preserving watchlist quote events and alert notifications.

**Architecture:** Reuse the existing `MarketQuoteProducer` service behind a dedicated worker entrypoint. Move market event subscriber registration into shared runtime helpers so the worker owns quote production and watchlist alerts, while the web app stops starting the producer.

**Tech Stack:** FastAPI lifespan hooks, SQLAlchemy sessions, existing hybrid event bus, Python worker entrypoints, pytest

---

## Chunk 1: Worker Extraction

### Task 1: Add failing tests for worker runtime ownership

**Files:**
- Modify: `backend/tests/test_market_quote_producer.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/workers/market_quote_producer.py`

- [ ] **Step 1: Write failing tests**

Cover:
- market quote worker `main()` initializes DB, registers market handlers, and starts producer
- FastAPI lifespan no longer starts or stops the market producer

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_market_quote_producer.py -q`
Expected: FAIL because the worker module does not exist and app lifespan still owns the producer.

- [ ] **Step 3: Implement minimal worker extraction**

Add a worker entrypoint and remove producer start/stop from app lifespan. Keep helper functions small and explicit.

- [ ] **Step 4: Re-run focused tests**

Run: `conda run -n news-caught pytest backend/tests/test_market_quote_producer.py -q`
Expected: PASS.

### Task 2: Preserve watchlist alert behavior under worker-owned runtime

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_market.py`

- [ ] **Step 1: Add failing test expectations if needed**

Ensure the existing alert test uses runtime registration that the worker would also use.

- [ ] **Step 2: Refactor event-handler registration**

Extract shared market-handler wiring so the worker can register watchlist alert subscribers without relying on FastAPI startup.

- [ ] **Step 3: Re-run market tests**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS.

## Chunk 2: Developer Run Path And Docs

### Task 3: Update commands and docs

**Files:**
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Add worker run command**

Expose a `make market-worker` target mirroring the existing worker style.

- [ ] **Step 2: Update README**

Document that:
- web app no longer owns the market quote producer
- users should run the dedicated worker for continuous行情 production

- [ ] **Step 3: Update code change log**

Record the worker extraction, runtime impact, commands, and verification.

## Chunk 3: Verification

### Task 4: Run final checks

**Files:**
- No code changes

- [ ] **Step 1: Run focused regression**

Run: `conda run -n news-caught pytest backend/tests/test_market_quote_producer.py backend/tests/test_market.py -q`
Expected: PASS.

- [ ] **Step 2: Run full backend verification**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS.
