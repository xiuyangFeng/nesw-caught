# Dashboard Movers Summary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compress the dashboard abnormal movers module into a summary-first entry point that shows only representative items plus a link to the full watchlist.

**Architecture:** Keep all data sourcing in `marketStore.abnormalMovers`, compute summary metadata locally inside `DashboardView.vue`, and preserve the Watchlist page as the only full-detail destination. Verification focuses on a targeted view test plus a production build.

**Tech Stack:** Vue 3, Pinia, Vue Test Utils, Vitest, Vite

---

## Chunk 1: Lock The New Dashboard Behavior

### Task 1: Add a failing dashboard view test for summary-first movers

**Files:**
- Modify: `frontend/src/views/DashboardView.test.ts`
- Test: `frontend/src/views/DashboardView.test.ts`

- [ ] **Step 1: Write the failing test**

Add assertions that the abnormal movers module:
- renders a summary string for total movers
- renders a “查看全部异动” entry link
- limits rendered representative mover rows to 3

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`
Expected: FAIL because the current component still renders the full list and has no summary CTA.

## Chunk 2: Implement The Summary Panel

### Task 2: Add local dashboard aggregations and compact panel layout

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`
- Test: `frontend/src/views/DashboardView.test.ts`

- [ ] **Step 1: Add computed summary helpers**

In `DashboardView.vue`, add computed values for:
- preview items limited to 3
- market counts by `hk` / `us` / `cn`
- most common abnormal reason with a safe fallback label

- [ ] **Step 2: Replace the long movement list markup**

Update the `Live Movers` card to render:
- a summary header
- the limited representative list
- a bottom `RouterLink` to `/watchlist`

- [ ] **Step 3: Refresh styles for the compact card**

Adjust the scoped CSS to support:
- a denser summary block
- slimmer representative rows
- a clear bottom CTA that matches the terminal theme

- [ ] **Step 4: Run the targeted test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`
Expected: PASS

## Chunk 3: Regression Verification And Logging

### Task 3: Verify surrounding frontend behavior and record the change

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused frontend verification**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`
Expected: PASS

- [ ] **Step 2: Run production build**

Run: `npm --prefix frontend run build`
Expected: build succeeds with exit code 0

- [ ] **Step 3: Update the code change log**

Append a new top entry in `docs/code-change-log.md` describing:
- dashboard movers summary redesign
- files touched
- verification commands run
- any residual risks around reason text mapping or ordering
