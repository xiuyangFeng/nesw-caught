# Runtime Status Store Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract frontend runtime health into a dedicated global store so shell and watchlist views no longer depend on watchlist business loading for worker status.

**Architecture:** Add a focused `runtimeStatusStore` that owns `/api/stream/status` and `market_worker`, refactor `AppShell` and `WatchlistView` to consume it directly, and remove runtime fetches from `watchlistStore`. Keep manual market refresh in `watchlistStore`, but have it trigger a runtime refresh after success so infrastructure and business panels stay aligned.

**Tech Stack:** Vue 3, Pinia, Vitest, Vite

---

## Chunk 1: Runtime Store And Consumer Refactor

### Task 1: Add failing tests for the new runtime store

**Files:**
- Create: `frontend/src/stores/runtimeStatusStore.test.ts`
- Create: `frontend/src/stores/runtimeStatusStore.ts`
- Test: `frontend/src/stores/runtimeStatusStore.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it('loads stream status and exposes market worker status', async () => {
  apiClient.getStreamStatus.mockResolvedValue({
    data: {
      mode: 'sse',
      status: 'ok',
      backend: 'hybrid',
      redis_enabled: true,
      last_published_at: null,
      last_event_name: null,
      last_error: null,
      market_worker: { name: 'market_quote_producer', status: 'ok', ... },
    },
    degraded: false,
  });

  await store.loadRuntimeStatus();

  expect(store.marketWorkerStatus?.status).toBe('ok');
  expect(store.streamStatus?.backend).toBe('hybrid');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts`

Expected: FAIL because `runtimeStatusStore.ts` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `runtimeStatusStore.ts` with `streamStatus`, `marketWorkerStatus`, `loading`, `error`, `lastLoadedAt`, and `loadRuntimeStatus()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts`

Expected: PASS

### Task 2: Refactor AppShell and WatchlistView to consume runtime store

**Files:**
- Modify: `frontend/src/components/layout/AppShell.vue`
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Test: `frontend/src/components/layout/AppShell.test.ts`
- Test: `frontend/src/views/WatchlistView.test.ts`

- [ ] **Step 1: Write the failing consumer tests**

Update tests so `AppShell` and `WatchlistView` mock `useRuntimeStatusStore()` instead of `watchlistStore.marketWorkerStatus`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts src/views/WatchlistView.test.ts`

Expected: FAIL because components still read runtime data from `watchlistStore`.

- [ ] **Step 3: Write minimal implementation**

Refactor components to read `marketWorkerStatus` from the runtime store and have `AppShell.bootstrap()` call `runtimeStatusStore.loadRuntimeStatus()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts src/views/WatchlistView.test.ts`

Expected: PASS

## Chunk 2: Watchlist Store Decoupling

### Task 3: Remove runtime fetching from watchlist store and keep manual refresh linkage

**Files:**
- Modify: `frontend/src/stores/watchlistStore.ts`
- Modify: `frontend/src/stores/watchlistStore.test.ts`
- Test: `frontend/src/stores/watchlistStore.test.ts`

- [ ] **Step 1: Write the failing decoupling tests**

Add or update tests to assert:

- `loadWatchlist()` only calls `getWatchlist()` and `getWatchlistQuotes()`
- `refreshMarketQuotes()` triggers `runtimeStatusStore.loadRuntimeStatus()` after success

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`

Expected: FAIL because the store still calls `getStreamStatus()` directly and does not invoke the runtime store.

- [ ] **Step 3: Write minimal implementation**

Remove `marketWorkerStatus` from `watchlistStore`, stop calling `apiClient.getStreamStatus()` inside `loadWatchlist()`, and call `runtimeStatusStore.loadRuntimeStatus()` after successful manual refresh.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`

Expected: PASS

### Task 4: Verify integrated frontend behavior and record the change

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused frontend verification**

Run: `npm --prefix frontend run test -- --run src/stores/runtimeStatusStore.test.ts src/stores/watchlistStore.test.ts src/components/layout/AppShell.test.ts src/views/WatchlistView.test.ts`

Expected: PASS

- [ ] **Step 2: Run build verification**

Run: `npm --prefix frontend run build`

Expected: PASS

- [ ] **Step 3: Update change log**

Add a top entry describing the runtime status store extraction, touched files, validation evidence, and residual risks.
