# Feishu Notification Bugfix Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix incorrect news notification selection, duplicate watchlist alerts, and mock secret preservation for Feishu notification settings.

**Architecture:** Keep the current Feishu integration structure, but move news notification input from inferred recency queries to explicit inserted-item tracking, and move watchlist alert dispatch from stateless threshold checks to edge-triggered in-memory state. Lock both regressions with failing tests before editing production code.

**Tech Stack:** FastAPI, SQLAlchemy, Python, pytest, Vue 3, TypeScript, Vitest

---

## Chunk 1: Lock Backend Regressions

### Task 1: Add a failing regression test for refresh notifications

**Files:**
- Modify: `backend/tests/test_news_ingestion.py`
- Modify: `backend/app/services/news_ingestion.py`
- Modify: `backend/app/api/routes/news.py`

- [ ] **Step 1: Write the failing test**

Add a route-level test that patches `NewsIngestionService.refresh_all()` to return one inserted item and patches `get_notification_service()` with a recorder. Assert that the route forwards exactly that inserted item to `on_news_created()` and does not query recency reconstruction.

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q`
Expected: FAIL because `RefreshSummary` and the route do not yet carry explicit inserted items.

- [ ] **Step 3: Write minimal implementation**

Add inserted-item tracking through the ingestion summary and use it inside `/api/news/refresh`.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q`
Expected: PASS

### Task 2: Add a failing regression test for duplicate watchlist alerts

**Files:**
- Modify: `backend/tests/test_market.py`
- Modify: `backend/app/api/routes/market.py`
- Modify: `backend/app/services/notification_service.py`

- [ ] **Step 1: Write the failing test**

Add a route-level test that loads the watchlist quotes endpoint multiple times with a recorder notification service. Assert that a symbol crossing above threshold alerts once, stays silent while still above threshold, resets after falling back inside threshold, and alerts again on a later re-entry.

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: FAIL because the current route sends every time the threshold is exceeded.

- [ ] **Step 3: Write minimal implementation**

Teach `NotificationService` to track threshold state per symbol and only notify on `False -> True`.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS

## Chunk 2: Lock Frontend Mock Compatibility

### Task 3: Add a failing frontend regression test for `app_secret_set`

**Files:**
- Create: `frontend/src/api/client.test.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Write the failing test**

Stub `fetch` to reject so the API client takes the mock fallback path. Seed `mockFeishuConfig.app_secret_set = true`, save a config payload without `app_secret`, and assert the returned config still has `app_secret_set = true`.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts`
Expected: FAIL because the fallback currently overwrites the flag to `false`.

- [ ] **Step 3: Write minimal implementation**

Preserve the existing mock `app_secret_set` flag when no new secret is provided.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts`
Expected: PASS

## Chunk 3: Verification And Records

### Task 4: Update records and run focused verification

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log**

Add a top entry describing the notification bugfixes, affected files, validation, and residual risks.

- [ ] **Step 2: Run backend regression coverage**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_market.py backend/tests/test_feishu_notify.py -q`
Expected: PASS

- [ ] **Step 3: Run frontend regression coverage**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts`
Expected: PASS

- [ ] **Step 4: Run production build**

Run: `npm --prefix frontend run build`
Expected: PASS
