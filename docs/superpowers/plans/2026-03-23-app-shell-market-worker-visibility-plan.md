# App Shell Market Worker Visibility Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface market-worker runtime health in the global app shell.

**Architecture:** Reuse `watchlistStore.marketWorkerStatus`, which is already loaded during shell bootstrap, and render a compact worker-health summary in the existing `System Status` panel.

**Tech Stack:** Vue 3, Pinia, existing AppShell tests, Vite build

---

## Chunk 1: TDD For Shell Rendering

### Task 1: Add failing tests for market-worker shell status

**Files:**
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Modify: `frontend/src/components/layout/AppShell.vue`

- [ ] **Step 1: Write failing tests**

Cover:
- shell renders `market-worker` name and status
- shell renders degraded error summary when present

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: FAIL because AppShell does not yet render market-worker status.

- [ ] **Step 3: Implement minimal shell UI updates**

Render the status in the existing system-status block and keep the layout compact.

- [ ] **Step 4: Re-run focused tests**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: PASS.

## Chunk 2: Verification

### Task 2: Update change log and verify

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update code change log**

Record that global shell now exposes market-worker health.

- [ ] **Step 2: Run focused verification**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: PASS.

- [ ] **Step 3: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS.
