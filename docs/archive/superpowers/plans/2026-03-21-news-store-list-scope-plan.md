# News Store List Scope Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate dashboard, feed, and sentiment news list state inside `newsStore` so one page's filtered list no longer pollutes another page.

**Architecture:** Keep detail and analysis caches shared, but split list/query/loading state into dashboard/feed/sentiment slots. First add failing tests around the store and affected views, then update the store API and page consumers, and finally run full frontend verification and update the change log.

**Tech Stack:** Vue 3, Pinia, Vue Router, Vitest

---

## Chunk 1: Regression Guards

### Task 1: Add a failing store test for list-slot isolation

**Files:**
- Create: `frontend/src/stores/newsStore.test.ts`

- [ ] **Step 1: Write the failing test**

Assert that loading dashboard news and then loading sentiment news keeps `dashboardItems` unchanged while filling `sentimentItems`.

- [ ] **Step 2: Run the focused store test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/stores/newsStore.test.ts`
Expected: FAIL because scoped list APIs and state do not exist yet.

### Task 2: Add failing view/shell tests for the new store API

**Files:**
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Modify: `frontend/src/views/DashboardView.test.ts`
- Modify: `frontend/src/views/NewsFeedView.test.ts`
- Modify: `frontend/src/views/SentimentNewsView.test.ts`

- [ ] **Step 1: Update the tests to consume scoped store fields and methods**

Make the tests expect:
- `AppShell` calls `loadDashboardNews`
- `DashboardView` reads dashboard list state
- `NewsFeedView` reads feed list state and calls `loadFeedNews`
- `SentimentNewsView` reads sentiment list state and calls `loadSentimentNews`

- [ ] **Step 2: Run the focused test set to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts src/views/DashboardView.test.ts src/views/NewsFeedView.test.ts src/views/SentimentNewsView.test.ts`
Expected: FAIL because the components still use the old shared list API.

## Chunk 2: Store Refactor

### Task 3: Split `newsStore` list state by page scope

**Files:**
- Modify: `frontend/src/stores/newsStore.ts`

- [ ] **Step 1: Add dashboard/feed/sentiment list slots**

Introduce separate items, query, loading, and last-loaded state for each scope.

- [ ] **Step 2: Add explicit scoped load and refresh methods**

Implement `loadDashboardNews`, `loadFeedNews`, `loadSentimentNews`, and `refreshDashboardNews`.

- [ ] **Step 3: Update `upsertNews` to insert into matching slots only**

Use query matching so SSE updates reach the right lists without leaking across scopes.

- [ ] **Step 4: Run the focused store test**

Run: `npm --prefix frontend run test -- --run src/stores/newsStore.test.ts`
Expected: PASS.

## Chunk 3: Consumer Migration

### Task 4: Move pages and shell to scoped store APIs

**Files:**
- Modify: `frontend/src/components/layout/AppShell.vue`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/views/NewsFeedView.vue`
- Modify: `frontend/src/views/SentimentNewsView.vue`

- [ ] **Step 1: Bootstrap dashboard scope from `AppShell`**

Replace the old shared news bootstrap with dashboard-specific loading and refresh.

- [ ] **Step 2: Migrate `DashboardView` to dashboard slot**

Use dashboard items/loading/staleness for metrics and latest-news preview.

- [ ] **Step 3: Migrate `NewsFeedView` to feed slot**

Use feed items/loading/staleness and update filter watchers to call `loadFeedNews`.

- [ ] **Step 4: Migrate `SentimentNewsView` to sentiment slot**

Use sentiment items/loading/staleness and call `loadSentimentNews`.

- [ ] **Step 5: Run the focused consumer tests**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts src/views/DashboardView.test.ts src/views/NewsFeedView.test.ts src/views/SentimentNewsView.test.ts`
Expected: PASS.

## Chunk 4: Verification And Record

### Task 5: Update records and verify the frontend

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the change log**

Record the list-scope refactor, touched files, verification evidence, and remaining risks.

- [ ] **Step 2: Run full frontend verification**

Run: `npm --prefix frontend run test -- --run`
Expected: PASS.

Run: `npm --prefix frontend run build`
Expected: PASS.
