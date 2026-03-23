# Stream Status Request Dedup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deduplicate frontend `/api/stream/status` requests by making `runtimeStatusStore` the only fetch owner and turning `connectionStore` into a pure SSE connection state store.

**Architecture:** Extend `runtimeStatusStore` to persist `usingMock`, add a snapshot-apply entrypoint to `connectionStore`, and refactor `AppShell` bootstrap to hydrate the connection store from runtime state instead of issuing a second status request. Keep page-level consumers unchanged.

**Tech Stack:** Vue 3, Pinia, Vitest, Vite

---

## Chunk 1: Store Boundary Refactor

### Task 1: Add failing tests for runtime and connection store status handoff

**Files:**
- Modify: `frontend/src/stores/runtimeStatusStore.test.ts`
- Create: `frontend/src/stores/connectionStore.test.ts`
- Test: `frontend/src/stores/runtimeStatusStore.test.ts`
- Test: `frontend/src/stores/connectionStore.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests asserting:

- `runtimeStatusStore.loadRuntimeStatus()` persists `usingMock`
- `connectionStore.applyStreamStatus()` sets `streamStatus`, `usingMock`, and initial `state`

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/stores/connectionStore.test.ts`

Expected: FAIL because `runtimeStatusStore` does not expose `usingMock` and `connectionStore` does not have `applyStreamStatus()`.

- [ ] **Step 3: Write minimal implementation**

Add `usingMock` to `runtimeStatusStore` and `applyStreamStatus()` to `connectionStore`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/stores/connectionStore.test.ts`

Expected: PASS

### Task 2: Refactor AppShell bootstrap to remove duplicate request

**Files:**
- Modify: `frontend/src/components/layout/AppShell.vue`
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Test: `frontend/src/components/layout/AppShell.test.ts`

- [ ] **Step 1: Write the failing shell test**

Update the shell test to assert:

- `runtimeStatusStore.loadRuntimeStatus()` is called
- `connectionStore.loadStreamStatus()` is not called
- `connectionStore.applyStreamStatus()` is called with the runtime snapshot

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`

Expected: FAIL because `AppShell` still calls `connectionStore.loadStreamStatus()` directly.

- [ ] **Step 3: Write minimal implementation**

Refactor bootstrap so runtime status loads first and hydrates `connectionStore` through `applyStreamStatus()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`

Expected: PASS

## Chunk 2: Verification And Recording

### Task 3: Run focused verification and update change log

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused test verification**

Run: `npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/stores/connectionStore.test.ts src/components/layout/AppShell.test.ts src/stores/watchlistStore.test.ts src/views/WatchlistView.test.ts`

Expected: PASS

- [ ] **Step 2: Run build verification**

Run: `npm --prefix frontend run build`

Expected: PASS

- [ ] **Step 3: Update change log**

Record the stream status request dedup change, affected files, verification commands, and any residual risks.
