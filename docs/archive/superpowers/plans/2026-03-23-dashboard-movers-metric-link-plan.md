# Dashboard Movers Metric Link Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Dashboard "异动股票" hero metric card clickable so it routes to `/watchlist`.

**Architecture:** Reuse the existing `HeroMetrics` route-backed card path by adding a `to` target for the movers metric in `DashboardView`. Keep the component contract unchanged and verify the route mapping via view tests.

**Tech Stack:** Vue 3, Vue Router, Vitest, Vite

---

## Chunk 1: Dashboard Metric Route Mapping

### Task 1: Add failing Dashboard tests for the movers metric link

**Files:**
- Modify: `frontend/src/views/DashboardView.test.ts`
- Modify: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: Write the failing test**

Add a test asserting that the Dashboard hero metrics include a `/watchlist` link for the "异动股票" card.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`

Expected: FAIL because the movers metric is still static.

- [ ] **Step 3: Write minimal implementation**

Add `to: '/watchlist'` to the movers metric definition in `DashboardView`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`

Expected: PASS

## Chunk 2: Verification And Recording

### Task 2: Verify and record the change

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused view tests**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`

Expected: PASS

- [ ] **Step 2: Run build verification**

Run: `npm --prefix frontend run build`

Expected: PASS

- [ ] **Step 3: Update change log**

Record the Dashboard metric-card navigation enhancement and verification evidence.
