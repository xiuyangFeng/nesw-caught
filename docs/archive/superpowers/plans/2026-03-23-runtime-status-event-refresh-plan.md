# Runtime Status Event Refresh Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep runtime status fresher by triggering throttled refreshes after key SSE events without introducing a fixed polling loop.

**Architecture:** Add a store-owned `loadRuntimeStatusIfStale()` gate that deduplicates refreshes by age and in-flight state, then have `AppShell` call it after `watchlist.movement` and `stream.keepalive` events. Keep the request source centralized in `runtimeStatusStore`.

**Tech Stack:** Vue 3, Pinia, Vitest, Vite

---

## Chunk 1: Store-Side Throttled Refresh

### Task 1: Add failing tests for stale-gated runtime refresh

**Files:**
- Modify: `frontend/src/stores/runtimeStatusStore.test.ts`
- Modify: `frontend/src/stores/runtimeStatusStore.ts`
- Test: `frontend/src/stores/runtimeStatusStore.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests asserting:

- `loadRuntimeStatusIfStale()` skips a second request when `lastLoadedAt` is still fresh
- it does request again when `lastLoadedAt` is older than the threshold

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts`

Expected: FAIL because the store does not expose `loadRuntimeStatusIfStale()`.

- [ ] **Step 3: Write minimal implementation**

Add `loadRuntimeStatusIfStale(maxAgeSeconds = 15)` using `lastLoadedAt`, `loading`, and the existing `loadRuntimeStatus()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts`

Expected: PASS

### Task 2: Trigger throttled refreshes from AppShell SSE events

**Files:**
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Modify: `frontend/src/components/layout/AppShell.vue`
- Test: `frontend/src/components/layout/AppShell.test.ts`

- [ ] **Step 1: Write the failing shell tests**

Update shell tests to assert:

- `watchlist.movement` causes `runtimeStatusStore.loadRuntimeStatusIfStale()` to run
- `stream.keepalive` also causes `runtimeStatusStore.loadRuntimeStatusIfStale()` to run

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`

Expected: FAIL because the event handler does not invoke the throttled refresh entry.

- [ ] **Step 3: Write minimal implementation**

Call `runtimeStatusStore.loadRuntimeStatusIfStale()` in those event branches.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`

Expected: PASS

## Chunk 2: Verification And Recording

### Task 3: Run focused verification and update change log

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused tests**

Run: `npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/components/layout/AppShell.test.ts src/stores/connectionStore.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`

Expected: PASS

- [ ] **Step 2: Run build verification**

Run: `npm --prefix frontend run build`

Expected: PASS

- [ ] **Step 3: Update change log**

Record the event-driven runtime refresh change, verification commands, and remaining freshness limits.
