# Dashboard Sentiment News Entry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the dashboard positive/negative sentiment metrics into drill-down entry points that open a dedicated sentiment news list page and then the existing news detail page.

**Architecture:** Keep the backend unchanged. First add failing frontend tests that describe the new navigation contract, then extend the metric component to support optional routes, add a dedicated sentiment-news view plus router entry, and finally update the change log and run full frontend verification.

**Tech Stack:** Vue 3, Vue Router, Pinia, Vitest

---

## Chunk 1: Dashboard Entry Regression Guard

### Task 1: Describe the new metric-card navigation contract

**Files:**
- Modify: `frontend/src/components/dashboard/HeroMetrics.test.ts`
- Modify: `frontend/src/views/DashboardView.test.ts`

- [ ] **Step 1: Write a failing component test for clickable metrics**

Assert that a metric with a route renders as a clickable link/button target while metrics without routes remain static cards.

- [ ] **Step 2: Write a failing dashboard test for sentiment entry routes**

Assert that the dashboard renders `偏利好` and `偏利空` cards with targets for `/news/sentiment/positive` and `/news/sentiment/negative`.

- [ ] **Step 3: Run the focused tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/components/dashboard/HeroMetrics.test.ts src/views/DashboardView.test.ts`
Expected: FAIL because the current metrics model has no route field and cards are not clickable.

## Chunk 2: Dedicated Sentiment News View

### Task 2: Add a failing view test for the sentiment news page

**Files:**
- Create: `frontend/src/views/SentimentNewsView.test.ts`

- [ ] **Step 1: Write the failing test**

Mount the new view with mocked route/store data and assert:
- it requests the expected `sentiment_label`
- it renders news in descending timestamp order
- it shows summary/source/time/mentions for each card
- clicking a card pushes to the existing news-detail route

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/SentimentNewsView.test.ts`
Expected: FAIL because the route/view does not exist yet.

## Chunk 3: Minimal Implementation

### Task 3: Make the dashboard metrics navigable

**Files:**
- Modify: `frontend/src/components/dashboard/HeroMetrics.vue`
- Modify: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: Extend metric typing with optional route metadata**

Add an optional route target for clickable metric cards while preserving existing tones and text.

- [ ] **Step 2: Render route-backed metrics as interactive cards**

Use the existing visual shell but switch to `RouterLink` for metrics that carry routes.

- [ ] **Step 3: Point positive/negative dashboard metrics at the new routes**

Set the two sentiment cards to `/news/sentiment/positive` and `/news/sentiment/negative`.

- [ ] **Step 4: Re-run the focused dashboard tests**

Run: `npm --prefix frontend run test -- --run src/components/dashboard/HeroMetrics.test.ts src/views/DashboardView.test.ts`
Expected: PASS.

### Task 4: Build the sentiment news list page

**Files:**
- Create: `frontend/src/views/SentimentNewsView.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Read the route sentiment and normalize it**

Accept only `positive` and `negative`, default invalid values to `positive`.

- [ ] **Step 2: Load sentiment-scoped news and hydrate details**

Call `newsStore.loadNews({ sentiment_label, limit: 300 })`, then load per-item detail as needed for richer cards.

- [ ] **Step 3: Render a time-descending structured card list**

Show title, source, market, time, summary, sentiment label, and mentions; clicking a card should open the existing detail route.

- [ ] **Step 4: Register the new route**

Add the new dedicated route to the Vue router without disturbing existing news/detail routes.

- [ ] **Step 5: Re-run the focused view test**

Run: `npm --prefix frontend run test -- --run src/views/SentimentNewsView.test.ts`
Expected: PASS.

## Chunk 4: Verification And Record

### Task 5: Update records and run project verification

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the change log**

Append a top entry that records the new dashboard sentiment entry flow, touched files, verification evidence, and remaining risks.

- [ ] **Step 2: Run the frontend regression suite**

Run: `npm --prefix frontend run test -- --run src/components/dashboard/HeroMetrics.test.ts src/views/DashboardView.test.ts src/views/SentimentNewsView.test.ts`
Expected: PASS.

- [ ] **Step 3: Run the full frontend verification**

Run: `npm --prefix frontend run test -- --run`
Expected: PASS.

Run: `npm --prefix frontend run build`
Expected: PASS.
