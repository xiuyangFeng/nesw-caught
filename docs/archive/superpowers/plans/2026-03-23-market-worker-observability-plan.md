# Market Worker Observability Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the independent market quote worker runtime status and expose it through the existing stream status API.

**Architecture:** Add a small database-backed runtime-status store, update `MarketQuoteProducer` to write heartbeat/success/failure status every cycle, and extend `/api/stream/status` to include the persisted `market_worker` payload.

**Tech Stack:** SQLAlchemy models/repositories, FastAPI route/schema updates, pytest

---

## Chunk 1: Runtime Status Persistence

### Task 1: Add failing tests for producer status writes

**Files:**
- Modify: `backend/tests/test_market_quote_producer.py`
- Create: `backend/app/models/worker_runtime_status.py`
- Create: `backend/app/repositories/worker_runtime_status_repository.py`
- Modify: `backend/app/services/market_quote_producer.py`

- [ ] **Step 1: Write failing tests**

Cover:
- successful producer cycle writes `ok` status, heartbeat, counts, and last quote count
- failed producer cycle writes `degraded` and last error

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_market_quote_producer.py -q`
Expected: FAIL because runtime status persistence does not exist.

- [ ] **Step 3: Implement minimal runtime status persistence**

Add the model/repository and update the producer to write status around each cycle.

- [ ] **Step 4: Re-run focused tests**

Run: `conda run -n news-caught pytest backend/tests/test_market_quote_producer.py -q`
Expected: PASS.

## Chunk 2: API Exposure

### Task 2: Add failing tests for stream status response

**Files:**
- Modify: `backend/tests/test_stream_status.py`
- Modify: `backend/app/schemas/stream.py`
- Modify: `backend/app/api/routes/stream.py`

- [ ] **Step 1: Write failing API tests**

Cover:
- `/api/stream/status` returns `market_worker`
- missing worker row returns `market_worker = null`

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_stream_status.py -q`
Expected: FAIL because the response model does not include `market_worker`.

- [ ] **Step 3: Implement API response**

Load runtime status from DB and serialize it into the status response.

- [ ] **Step 4: Re-run focused tests**

Run: `conda run -n news-caught pytest backend/tests/test_stream_status.py -q`
Expected: PASS.

## Chunk 3: Docs And Verification

### Task 3: Update docs and run verification

**Files:**
- Modify: `README.md`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update README**

Document that `/api/stream/status` now includes market worker runtime health.

- [ ] **Step 2: Update code change log**

Record the new status store, API field, and verification.

- [ ] **Step 3: Run focused verification**

Run: `conda run -n news-caught pytest backend/tests/test_market_quote_producer.py backend/tests/test_stream_status.py -q`
Expected: PASS.

- [ ] **Step 4: Run full backend verification**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS.
