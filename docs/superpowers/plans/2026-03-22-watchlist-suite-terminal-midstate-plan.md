# Watchlist Suite Terminal Midstate Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine Watchlist, Watchlist Detail, and Topic Detail into the agreed terminal midpoint without changing data or interaction behavior.

**Architecture:** Keep each route/component responsible for its current data flow and only refine presentational structure. Use TDD through focused test-anchor updates first, then implement the minimal styling and markup changes needed to satisfy those tests.

**Tech Stack:** Vue 3, Tailwind CSS, scoped CSS where already used, Vitest, Vue Test Utils

---

## File Map

- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/WatchlistView.test.ts`
- Modify: `frontend/src/components/watchlist/WatchlistTable.vue`
- Modify: `frontend/src/components/watchlist/WatchlistTable.test.ts`
- Modify: `frontend/src/views/WatchlistDetailView.vue`
- Modify: `frontend/src/views/WatchlistDetailView.test.ts`
- Modify: `frontend/src/views/TopicDetailView.vue`
- Modify: `frontend/src/views/TopicDetailView.test.ts`
- Modify: `docs/code-change-log.md`

## Chunk 1: Test-First Terminal Midstate Anchors

- [ ] **Step 1: Update Watchlist-related tests with the new visual anchors**
- [ ] **Step 2: Run targeted tests and verify failure**

Run:

```bash
npm --prefix frontend run test -- --run src/components/watchlist/WatchlistTable.test.ts src/views/WatchlistView.test.ts src/views/WatchlistDetailView.test.ts src/views/TopicDetailView.test.ts
```

Expected:
- FAIL on new structure anchors and tightened terminal-module markers

## Chunk 2: Implement Visual Refinement

- [ ] **Step 3: Refine WatchlistView control station and related-news panel**
- [ ] **Step 4: Refine WatchlistTable shell and row treatment**
- [ ] **Step 5: Refine WatchlistDetailView into a tighter single-symbol monitor**
- [ ] **Step 6: Refine TopicDetailView toolbar and source-card modules**
- [ ] **Step 7: Re-run targeted tests and verify pass**

## Chunk 3: Verification And Closeout

- [ ] **Step 8: Run focused suite covering this whole UI refinement arc**
- [ ] **Step 9: Run frontend build**
- [ ] **Step 10: Update `docs/code-change-log.md`**
- [ ] **Step 11: Request final review and fix any Important/Critical findings**
