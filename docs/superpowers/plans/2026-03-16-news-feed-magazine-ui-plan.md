# News Feed Magazine UI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the News Feed into a magazine-style reading surface with a full-width lead story, flowing secondary stories, stable editorial ranking, and a top-aligned editorial sidebar while eliminating headline overlap.

**Architecture:** Keep the existing API contract and move the change into the frontend presentation layer. Extract editorial ranking/grouping into a dedicated helper with unit tests, then rebuild the news index around magazine sections instead of the current fixed-height split layout. Sidebar and shared surface styling should be adjusted just enough to support the new reading hierarchy without refactoring unrelated pages.

**Tech Stack:** Vue 3, Pinia, Vue Router, TypeScript, Vitest, Vite

---

## Chunk 1: Editorial Ranking Foundation

### Task 1: Add frontend unit-test support and failing editorial ranking tests

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/utils/newsEditorial.test.ts`
- Create: `frontend/src/utils/newsEditorial.ts`

- [ ] **Step 1: Add failing test scaffolding**

Add `vitest` and a `test` script, plus a minimal `vitest.config.ts` that runs in a lightweight node/jsdom-safe setup for pure utility tests.

- [ ] **Step 2: Write failing editorial ranking tests**

Add tests that assert:
- higher `topic.importance_score` beats merely newer but low-context news
- recency still wins between otherwise similar stories
- missing detail data falls back to a stable, lower-confidence score
- grouped output returns exactly one `lead`, a bounded `supporting` set, and the remaining `stream`

- [ ] **Step 3: Run tests to verify failure**

Run: `npm --prefix frontend run test -- --run src/utils/newsEditorial.test.ts`
Expected: FAIL because the ranking/grouping helpers do not exist or return the wrong structure

- [ ] **Step 4: Implement minimal editorial helpers**

Create utilities that:
- compute `editorialScore` from list item + optional detail
- sort filtered items deterministically
- split stories into `lead`, `supporting`, and `stream`

- [ ] **Step 5: Re-run the utility tests**

Run: `npm --prefix frontend run test -- --run src/utils/newsEditorial.test.ts`
Expected: PASS

## Chunk 2: News Feed Layout Rewrite

### Task 2: Add failing integration points for the magazine feed

**Files:**
- Modify: `frontend/src/views/NewsFeedView.vue`
- Modify: `frontend/src/components/news/NewsCard.vue`
- Create: `frontend/src/components/news/LeadStoryCard.vue`
- Create: `frontend/src/components/news/StoryStrip.vue`
- Modify: `frontend/src/components/common/SectionCard.vue`

- [ ] **Step 1: Introduce failing references to the new structure**

Update `NewsFeedView.vue` to reference:
- editorial grouping helpers
- `LeadStoryCard.vue`
- `StoryStrip.vue`
- the removal of the split persistent detail panel

- [ ] **Step 2: Run frontend build to verify failure**

Run: `npm --prefix frontend run build`
Expected: FAIL because the new components and grouping flow are not implemented yet

- [ ] **Step 3: Implement the minimal magazine layout**

Change the news page so it renders:
- compact edition header with lightweight filters
- one full-width lead story
- a small set of supporting stories
- a flowing stream of standard cards below

Keep story selection and navigation to `/news/:id` intact.

- [ ] **Step 4: Rework shared card primitives just enough**

Adjust `NewsCard.vue` and `SectionCard.vue` so:
- long Chinese headlines wrap cleanly
- summaries clamp intentionally
- metadata stays readable
- cards support variable-height content without overlap

- [ ] **Step 5: Re-run frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS or fail only on sidebar/style work

## Chunk 3: Remove Fixed-Height List Constraints

### Task 3: Replace the fixed-height virtual list path with variable-height rendering

**Files:**
- Modify: `frontend/src/components/news/NewsVirtualList.vue`
- Modify: `frontend/src/composables/useVirtualList.ts`
- Modify: `frontend/src/views/NewsFeedView.vue`

- [ ] **Step 1: Add a failing regression test or typed integration breakpoint**

Make the feed no longer depend on a fixed `184px` row contract, so the old virtual-list usage becomes invalid and the build fails until the page is rewired.

- [ ] **Step 2: Run frontend build to verify failure**

Run: `npm --prefix frontend run build`
Expected: FAIL because the page still expects the old virtual-list API

- [ ] **Step 3: Implement the minimal replacement**

For the news index:
- stop using the fixed-height virtual list
- render normal flowing sections/cards
- keep `NewsVirtualList.vue` either unused, simplified, or removed from the news page path without refactoring unrelated pages

- [ ] **Step 4: Re-run tests and build**

Run:
- `npm --prefix frontend run test -- --run src/utils/newsEditorial.test.ts`
- `npm --prefix frontend run build`

Expected: PASS

## Chunk 4: Sidebar and Surface Polish

### Task 4: Add failing sidebar/layout expectations and implement the editorial shell

**Files:**
- Modify: `frontend/src/components/layout/AppShell.vue`
- Modify: `frontend/src/assets/main.css`
- Modify: `frontend/src/views/NewsFeedView.vue`

- [ ] **Step 1: Add failing layout references**

Update `AppShell.vue` to reference:
- a top-aligned sidebar structure
- grouped brand / nav / status blocks
- calmer active-state treatment that fits the editorial layout

- [ ] **Step 2: Run frontend build to verify failure**

Run: `npm --prefix frontend run build`
Expected: FAIL because the template/style changes are incomplete

- [ ] **Step 3: Implement the minimal sidebar and style polish**

Adjust shell/global styles so:
- sidebar is anchored from the top instead of visually centered
- page background and panels better support the magazine feel
- the news page gains stronger hierarchy without breaking other routes

- [ ] **Step 4: Re-run frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS

## Chunk 5: Verification and Documentation

### Task 5: Run full verification and update project records

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update change log entry**

Add a new top entry describing:
- news feed magazine layout
- editorial sorting helpers
- sidebar redesign
- frontend verification results

- [ ] **Step 2: Run frontend unit tests**

Run: `npm --prefix frontend run test -- --run`
Expected: PASS

- [ ] **Step 3: Run frontend build verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Perform manual browser spot checks**

Verify:
- long Chinese headlines no longer overlap
- one lead story is shown above supporting stories
- clicking a story still opens `/news/:id`
- sidebar no longer looks vertically centered on wide desktop layout

- [ ] **Step 5: Commit**

```bash
git add frontend docs/code-change-log.md
git commit -m "优化新闻页杂志流布局与侧栏"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-16-news-feed-magazine-ui-plan.md`. Ready to execute?
