# Runtime Status Low Frequency Polling Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a low-frequency runtime polling loop that keeps `/api/stream/status` reasonably fresh during idle periods without changing the existing SSE contract.

**Architecture:** Keep `runtimeStatusStore` as the single source for loading runtime snapshots and reuse `loadRuntimeStatusIfStale()` for both event-driven refreshes and a new AppShell-managed polling timer. The shell owns timer lifecycle; the store owns freshness and in-flight guards.

**Tech Stack:** Vue 3, Pinia, Vitest, Vite

---

## Chunk 1: Shell Polling Lifecycle

### Task 1: Add failing AppShell tests for low-frequency polling

**Files:**
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Modify: `frontend/src/components/layout/AppShell.vue`
- Test: `frontend/src/components/layout/AppShell.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests asserting:

- bootstrap completes, then schedules a low-frequency polling timer
- when the timer fires, `runtimeStatusStore.loadRuntimeStatusIfStale(45)` is called
- unmount clears the timer
- existing `watchlist.movement` and `stream.keepalive` refresh triggers still run

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`

Expected: FAIL because `AppShell` does not yet create or clean up a polling timer.

- [ ] **Step 3: Write minimal implementation**

Add a shell-owned polling interval that:

- starts after bootstrap
- calls `runtimeStatusStore.loadRuntimeStatusIfStale(45)`
- clears on `onBeforeUnmount`

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`

Expected: PASS

## Chunk 2: Verification And Project Recording

### Task 2: Run focused verification and update project records

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused frontend tests**

Run: `npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/components/layout/AppShell.test.ts src/stores/connectionStore.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`

Expected: PASS

- [ ] **Step 2: Run build verification**

Run: `npm --prefix frontend run build`

Expected: PASS

- [ ] **Step 3: Update change log**

Record the low-frequency polling change, verification commands, and the fact that runtime freshness still remains best-effort rather than true push-based observability.
