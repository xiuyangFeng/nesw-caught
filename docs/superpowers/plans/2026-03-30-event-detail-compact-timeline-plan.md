# Event Detail Compact Timeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compress event detail timeline news cards to an ultra-compact layout while preserving title, single-line summary, metadata, and both actions.

**Architecture:** Keep the current `EventDetailView` structure and route behavior intact, and tighten the card through targeted template class hooks plus scoped CSS updates. Lock the new density contract with a focused view test before touching production code.

**Tech Stack:** Vue 3, Vue Test Utils, Vitest, Vite, scoped CSS

---

## Chunk 1: Compact Timeline Card

### Task 1: Lock the compact contract in tests

**Files:**
- Modify: `frontend/src/views/EventDetailView.test.ts`
- Test: `frontend/src/views/EventDetailView.test.ts`

- [ ] **Step 1: Write the failing test**

Add assertions that the timeline summary node carries a compact summary hook and the action buttons carry a compact action hook.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/EventDetailView.test.ts`
Expected: FAIL because the compact hooks are not rendered yet.

- [ ] **Step 3: Write minimal implementation**

Update `frontend/src/views/EventDetailView.vue` to add the new hooks and tighten the timeline card spacing, typography, and control sizing.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/EventDetailView.test.ts`
Expected: PASS

### Task 2: Verify no layout regressions in build

**Files:**
- Modify: `frontend/src/views/EventDetailView.vue`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 2: Update change log**

Append a new top entry to `docs/code-change-log.md` describing the compact timeline card change, impacted files, validation, and residual risks.
