# Watchlist Detail Terminal Polish Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the pale metric and related-news cards in Watchlist detail with darker terminal cards.

**Architecture:** Keep the existing watchlist detail data loading and layout intact while adding explicit terminal surface hooks and updating only the view styles. Lock the new hooks with a failing test before editing production styles.

**Tech Stack:** Vue 3, TypeScript, Vitest, scoped CSS

---

## Chunk 1: Lock Terminal Card Hooks

### Task 1: Add a failing test for Watchlist detail terminal cards

**Files:**
- Create: `frontend/src/views/WatchlistDetailView.test.ts`
- Modify: `frontend/src/views/WatchlistDetailView.vue`

- [ ] **Step 1: Write the failing test**

```ts
expect(wrapper.find('[data-surface="terminal-metric-card"]').exists()).toBe(true);
expect(wrapper.find('[data-surface="terminal-related-card"]').exists()).toBe(true);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts`
Expected: FAIL because the new hooks do not exist yet.

- [ ] **Step 3: Add minimal implementation**

Add the `data-surface` hooks without changing data rendering behavior.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts`
Expected: PASS

## Chunk 2: Apply Darker Terminal Card Styling

### Task 2: Replace pale gray cards with dark terminal cards

**Files:**
- Modify: `frontend/src/views/WatchlistDetailView.vue`

- [ ] **Step 1: Darken metric cards**

Replace the current pale metric panel with the darker terminal surface and sharper text hierarchy.

- [ ] **Step 2: Darken related news cards**

Align related news cards with the darker terminal news-card treatment already used elsewhere.

## Chunk 3: Verification And Records

### Task 3: Update records and verify

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log**

Record the Watchlist detail metric/news card polish.

- [ ] **Step 2: Run targeted tests**

Run: `npm --prefix frontend run test -- --run src/views/WatchlistDetailView.test.ts`
Expected: PASS

- [ ] **Step 3: Run production build**

Run: `npm --prefix frontend run build`
Expected: PASS
