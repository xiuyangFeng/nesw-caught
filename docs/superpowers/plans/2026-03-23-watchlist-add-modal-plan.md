# Watchlist Add Modal Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current inline candidate click-to-add flow with a mixed-mode add-watchlist modal that supports both quick add and optional threshold configuration.

**Architecture:** Keep modal-only temporary state inside `WatchlistView` so the business store remains focused on real watchlist actions. Add a dedicated `WatchlistAddModal` component for search, candidate selection, and advanced settings, while `watchlistStore.createWatchlist()` continues to own submission/loading/error behavior.

**Tech Stack:** Vue 3, Pinia, Vitest, existing watchlist API/store, Tailwind utility styling

---

## Chunk 1: Modal Contract

### Task 1: Lock the modal UX in view tests

**Files:**
- Create: `frontend/src/components/watchlist/WatchlistAddModal.vue`
- Modify: `frontend/src/views/WatchlistView.test.ts`

- [ ] **Step 1: Write failing view tests for the modal flow**

Cover:
- clicking `搜索 / 添加自选股` opens the modal
- typing into the modal search shows candidate results
- clicking a candidate only selects it, but does not submit immediately
- clicking `直接添加` calls `createWatchlist`
- expanding advanced settings and filling threshold passes `alert_threshold`
- submission failure keeps the modal open and preserves error state

- [ ] **Step 2: Run the view tests and confirm they fail**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: FAIL because the modal component and event flow do not exist yet

- [ ] **Step 3: Build the modal component with minimal local state contract**

Implement `WatchlistAddModal.vue` with props for:
- `open`
- `candidates`
- `loading`
- `error`

And emits for:
- `close`
- `submit`

Keep candidate search and selection in the modal component; keep actual submission wiring in the page.

- [ ] **Step 4: Re-run the view tests**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: PASS

## Chunk 2: Page Wiring

### Task 2: Move add flow from sidebar inline actions to modal-driven flow

**Files:**
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/components/watchlist/WatchlistSidebar.vue`
- Create: `frontend/src/components/watchlist/WatchlistAddModal.vue`
- Modify: `frontend/src/types/api.ts` only if local helper types are needed

- [ ] **Step 1: Remove inline add submission from the sidebar and add an explicit modal trigger**

Replace the current candidate click-to-add path with:
- a top-left `搜索 / 添加自选股` entry button
- the existing `立即刷新一轮` action preserved separately

- [ ] **Step 2: Add page-local modal state**

Manage in `WatchlistView.vue`:
- `isAddModalOpen`
- `addModalQuery`
- `addModalSelectedCandidate`
- `addModalAdvancedOpen`
- `addModalAlertThreshold`

- [ ] **Step 3: Wire modal submit to the existing store**

On submit:
- call `watchlistStore.createWatchlist()`
- pass `alert_threshold` when provided
- keep `alert_mode="fixed"`
- on success close/reset modal and select the new symbol

- [ ] **Step 4: Preserve non-modal behavior**

Ensure:
- delete
- manual refresh
- runtime panel
- detail loading

continue to behave exactly as before.

- [ ] **Step 5: Re-run the targeted view tests**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts`
Expected: PASS

## Chunk 3: Regression Guardrails

### Task 3: Extend store-focused tests for create path expectations

**Files:**
- Modify: `frontend/src/stores/watchlistStore.test.ts`
- Modify: `frontend/src/stores/watchlistStore.ts` only if a small helper/refactor is needed

- [ ] **Step 1: Add or update store tests for create side effects**

Cover:
- successful create reloads watchlist data
- newly added symbol becomes selected
- create errors remain visible for the modal to render

- [ ] **Step 2: Run store tests to verify red/green**

Run: `npm --prefix frontend run test -- --run src/stores/watchlistStore.test.ts`
Expected: PASS after minimal store adjustments if needed

## Chunk 4: Verification and Records

### Task 4: Final verification and docs

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused frontend verification**

Run:
- `npm --prefix frontend run test -- --run src/views/WatchlistView.test.ts src/stores/watchlistStore.test.ts`
- `npm --prefix frontend run build`

Expected: both commands exit `0`

- [ ] **Step 2: Update code change log**

Append a new entry describing:
- add modal introduction
- advanced threshold option
- preserved runtime/delete/refresh behavior
- verification actually run
