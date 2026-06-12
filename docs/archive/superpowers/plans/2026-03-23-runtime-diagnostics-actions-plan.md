# Runtime Diagnostics And Action Guidance Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn raw runtime status fields into clear diagnostics and recommended actions in AppShell and Watchlist without changing backend contracts.

**Architecture:** Add a shared `runtimeDiagnostics` utility that derives a single actionable diagnostic from connection state, stream status, market worker status, and freshness timestamps. Keep components focused on presentation: AppShell shows alert + navigation guidance, Watchlist shows alert + direct remediation action.

**Tech Stack:** Vue 3, Pinia, Vue Router, Vitest, Vite

---

## Chunk 1: Shared Runtime Diagnostic Utility

### Task 1: Add failing tests for runtime diagnostic priority and messages

**Files:**
- Create: `frontend/src/utils/runtimeDiagnostics.test.ts`
- Create: `frontend/src/utils/runtimeDiagnostics.ts`

- [ ] **Step 1: Write the failing tests**

Add tests asserting:

- offline connection maps to an SSE-focused danger diagnostic
- degraded worker with recent error maps to a remediation diagnostic pointing to Watchlist
- missing worker runtime maps to a startup/configuration diagnostic
- stale worker heartbeat maps to a warning diagnostic
- healthy runtime maps to a success diagnostic

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/utils/runtimeDiagnostics.test.ts`

Expected: FAIL because the utility does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement a pure utility that returns a normalized diagnostic object with tone, headline, detail, action label, and action target.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/utils/runtimeDiagnostics.test.ts`

Expected: PASS

## Chunk 2: Shell And Watchlist Presentation

### Task 2: Add failing AppShell and Watchlist tests for diagnostic guidance

**Files:**
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/components/layout/AppShell.vue`
- Modify: `frontend/src/views/WatchlistView.vue`

- [ ] **Step 1: Write the failing tests**

Add tests asserting:

- AppShell renders the derived runtime diagnostic headline/detail and a Watchlist guidance link for worker issues
- Watchlist renders the same diagnostic headline/detail and explains the manual refresh button as the recommended action

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts src/views/WatchlistView.test.ts`

Expected: FAIL because the views do not yet render the shared diagnostic guidance.

- [ ] **Step 3: Write minimal implementation**

Wire the shared diagnostic utility into both components and render concise guidance text plus the appropriate action affordance.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts src/views/WatchlistView.test.ts`

Expected: PASS

## Chunk 3: Verification And Recording

### Task 3: Run focused verification and update project records

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused frontend tests**

Run: `npm --prefix frontend run test -- --run src/utils/runtimeDiagnostics.test.ts src/components/layout/AppShell.test.ts src/views/WatchlistView.test.ts src/stores/runtimeStatusStore.test.ts src/stores/watchlistStore.test.ts`

Expected: PASS

- [ ] **Step 2: Run build verification**

Run: `npm --prefix frontend run build`

Expected: PASS

- [ ] **Step 3: Update change log**

Record the new diagnostic guidance layer, affected views, verification commands, and any remaining limitations in the heuristic.
