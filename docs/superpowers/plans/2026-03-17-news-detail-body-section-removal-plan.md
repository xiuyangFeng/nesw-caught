# News Detail Body Section Removal Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the redundant article body section from the news detail page while keeping the original-source link as the only full-text entry point.

**Architecture:** Keep the backend and API contract unchanged, add a focused frontend regression test around `NewsDetailView`, then simplify the view so it no longer renders article extraction content or status. Finish by updating the repository change log and running frontend verification.

**Tech Stack:** Vue 3, Vue Router, Pinia, Vitest

---

## Chunk 1: Detail View Regression Guard

### Task 1: Add a failing test for redundant body-section removal

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vitest.config.ts`
- Create: `frontend/src/views/NewsDetailView.test.ts`

- [ ] **Step 1: Add test dependencies for Vue view testing**

Add the minimal dev dependencies needed to mount Vue SFC views under Vitest.

- [ ] **Step 2: Write the failing test**

Mount `NewsDetailView` with mocked route/store data and assert:
- the page still renders `打开原文`
- the page does not render `正文内容`
- the page does not render article extraction status text such as `success`

- [ ] **Step 3: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts`
Expected: FAIL because the current template still renders the body section.

## Chunk 2: View Simplification

### Task 2: Remove the redundant article body section

**Files:**
- Modify: `frontend/src/views/NewsDetailView.vue`

- [ ] **Step 1: Remove article-body computed usage if no longer needed**

Delete imports/computed values that only support the removed section.

- [ ] **Step 2: Remove the body `SectionCard` block**

Keep the header card, related information, and sibling navigation intact.

- [ ] **Step 3: Run the focused test**

Run: `npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts`
Expected: PASS.

## Chunk 3: Verification And Record

### Task 3: Update records and run frontend verification

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the change log**

Append a new top entry describing the detail-page simplification, touched files, verification evidence, and remaining scope boundaries.

- [ ] **Step 2: Run the full frontend verification**

Run: `npm --prefix frontend run test -- --run`
Expected: PASS.

Run: `npm --prefix frontend run build`
Expected: PASS.
