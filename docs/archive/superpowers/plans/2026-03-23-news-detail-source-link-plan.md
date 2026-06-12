# News Detail Source Link Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `News Feed -> News Detail` as the primary path while making the source article link an obvious action inside the detail page.

**Architecture:** Leave feed navigation unchanged. Strengthen the `NewsDetailView` metadata area by promoting `canonical_url` from a plain text link to a primary action button, with conditional rendering when the source URL is missing.

**Tech Stack:** Vue 3, Vue Router, Pinia, Vitest, Vite

---

## Chunk 1: Detail View Regression Test

### Task 1: Add failing tests for source-link visibility and behavior

**Files:**
- Modify: `frontend/src/views/NewsDetailView.test.ts`
- Modify: `frontend/src/views/NewsDetailView.vue`

- [ ] **Step 1: Write the failing test**

Add tests asserting:

- the detail view renders an obvious source action when `canonical_url` exists
- the action points to the expected URL with new-tab safety attributes
- the action is hidden when `canonical_url` is absent

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts`

Expected: FAIL because the detail view does not yet expose the promoted action affordance required by the new test.

- [ ] **Step 3: Write minimal implementation**

Promote the existing source link into a button-like anchor in the detail header and keep the render conditional on `canonical_url`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts`

Expected: PASS

## Chunk 2: Verification And Project Record

### Task 2: Run verification and update records

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused frontend verification**

Run: `npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts`

Expected: PASS

- [ ] **Step 2: Run build verification**

Run: `npm --prefix frontend run build`

Expected: PASS

- [ ] **Step 3: Update change log**

Record the detail-page source-link promotion, affected files, verification commands, and remaining UX limitations.
