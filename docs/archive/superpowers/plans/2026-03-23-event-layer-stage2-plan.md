# Event Layer Stage 2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move processed-news events, notification side effects, and watchlist market refresh side effects onto the shared event layer without changing the existing frontend SSE flow.

**Architecture:** Extend the hybrid event bus with additional event names and Redis stream mappings, make pipeline processing return a summary, publish `news.signals_processed`, `news.analysis_completed`, and `market.watchlist_refreshed`, and register local subscribers that keep the current notification behavior through event-driven orchestration instead of route-level direct calls.

**Tech Stack:** FastAPI, SQLAlchemy, Redis (redis-py), Python, pytest

---

## Chunk 1: Failing Tests For New Event Contracts

### Task 1: Add failing tests for processed-news, analysis, and market events

**Files:**
- Modify: `backend/tests/test_news_ingestion.py`
- Modify: `backend/tests/test_news_analysis.py`
- Modify: `backend/tests/test_market.py`
- Modify: `backend/tests/test_event_bus.py`
- Modify: `backend/tests/test_feishu_notify.py`

- [ ] **Step 1: Write the failing tests**

Add tests that:
- verify the news-created subscriber publishes `news.signals_processed`
- verify the news analyze route publishes `news.analysis_completed` instead of directly calling notification service
- verify the market watchlist route publishes `market.watchlist_refreshed`
- verify notification behavior can still be driven from event-facing methods

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_news_analysis.py backend/tests/test_market.py backend/tests/test_feishu_notify.py -q`
Expected: FAIL because the new event contracts and subscribers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Extend event bus stream mapping and implement only the event publishing/subscriber logic needed to satisfy the tests while preserving current behavior.

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_news_analysis.py backend/tests/test_market.py backend/tests/test_feishu_notify.py -q`
Expected: PASS

## Chunk 2: Event-Driven Notification Wiring

### Task 2: Move route-level notification side effects behind event subscribers

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/routes/news.py`
- Modify: `backend/app/api/routes/market.py`
- Modify: `backend/app/services/news_signal_pipeline.py`
- Modify: `backend/app/services/notification_service.py`
- Modify: `backend/app/services/event_bus.py`

- [ ] **Step 1: Add the failing regression assertions**

Ensure tests prove:
- route handlers no longer need direct notification service calls
- event subscribers can load required DB/config context and trigger the same outcomes

- [ ] **Step 2: Run the targeted tests to verify failure**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_news_analysis.py backend/tests/test_market.py -q`
Expected: FAIL before the subscriber wiring is complete.

- [ ] **Step 3: Implement the subscriber wiring**

Register event handlers in app startup for:
- `news.created_batch`
- `news.analysis_completed`
- `market.watchlist_refreshed`

Make pipeline processing return a summary and publish `news.signals_processed` after successful handling.

- [ ] **Step 4: Run targeted tests to verify pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_news_analysis.py backend/tests/test_market.py -q`
Expected: PASS

## Chunk 3: Records And Verification

### Task 3: Update records and run verification

**Files:**
- Modify: `docs/code-change-log.md`
- Modify: `README.md`

- [ ] **Step 1: Update docs and change log**

Document the new event names, notification/event responsibilities, and watchlist refresh event path.

- [ ] **Step 2: Run focused verification**

Run: `conda run -n news-caught pytest backend/tests/test_event_bus.py backend/tests/test_news_ingestion.py backend/tests/test_news_analysis.py backend/tests/test_market.py backend/tests/test_feishu_notify.py -q`
Expected: PASS

- [ ] **Step 3: Run full backend verification**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS
