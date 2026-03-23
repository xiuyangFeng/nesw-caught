# Redis Event Layer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Redis-backed hybrid event layer to the backend with automatic fallback to the existing in-process bus while keeping the current SSE/frontend behavior unchanged.

**Architecture:** Introduce a small Redis stream publisher plus a hybrid bus facade that always supports local subscribers and optionally publishes to Redis. Wire news refresh through the hybrid bus, expose real event-layer status through the stream status route, and keep the signal pipeline running through local subscribers so the user-facing flow remains stable.

**Tech Stack:** FastAPI, SQLAlchemy, Redis (redis-py), Python, pytest

---

## Chunk 1: Event Bus Tests And Config Surface

### Task 1: Add failing tests for hybrid event bus publish and fallback behavior

**Files:**
- Create: `backend/tests/test_event_bus.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/event_bus.py`
- Create: `backend/app/services/redis_stream_bus.py`

- [ ] **Step 1: Write the failing tests**

Add tests that:
- verify hybrid mode writes to Redis publisher and also calls local subscribers
- verify Redis publish failure still calls local subscribers and records degraded state
- verify memory mode skips Redis publishing
- verify default settings expose Redis event layer config values

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_event_bus.py -q`
Expected: FAIL because the hybrid Redis event layer and new settings do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add the Redis publisher abstraction, hybrid event bus facade, and config fields needed to satisfy the tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_event_bus.py -q`
Expected: PASS

## Chunk 2: Refresh Wiring And Status Endpoint

### Task 2: Add failing tests for refresh publishing and stream status reporting

**Files:**
- Modify: `backend/tests/test_news_ingestion.py`
- Create: `backend/tests/test_stream_status.py`
- Modify: `backend/app/services/news_ingestion.py`
- Modify: `backend/app/api/routes/stream.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing tests**

Add tests that:
- verify `refresh_all` publishes inserted news ids through the event layer instead of directly invoking the pipeline inline
- verify the locally subscribed pipeline still processes inserted news
- verify `/api/stream/status` reports event backend, status, and last error/last publish details

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_stream_status.py -q`
Expected: FAIL because refresh is not yet wired through the hybrid bus and stream status is still static.

- [ ] **Step 3: Write minimal implementation**

Initialize the hybrid bus in app lifecycle, register the local signal pipeline subscriber, publish refresh events from ingestion, and update the status route to read real event-layer health.

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_stream_status.py -q`
Expected: PASS

## Chunk 3: Records And Focused Verification

### Task 3: Update records and run verification

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log**

Add a top entry describing the Redis hybrid event layer, affected files, validation, and fallback behavior.

- [ ] **Step 2: Run focused backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_event_bus.py backend/tests/test_news_ingestion.py backend/tests/test_stream_status.py -q`
Expected: PASS

- [ ] **Step 3: Run broader backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_health.py backend/tests/test_news_ingestion.py backend/tests/test_news_signal_pipeline.py backend/tests/test_market.py backend/tests/test_x_monitor.py -q`
Expected: PASS
