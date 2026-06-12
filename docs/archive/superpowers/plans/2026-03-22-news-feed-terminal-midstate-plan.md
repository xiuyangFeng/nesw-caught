# News Feed Terminal Midstate Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine News Feed into the agreed terminal midpoint without changing its unified stream behavior.

**Architecture:** Keep `NewsFeedView` as the route owner and adjust only the presentational shell and `NewsCard` stream card treatment. Use TDD through focused visual-anchor tests first.

**Tech Stack:** Vue 3, Tailwind CSS, Vitest, Vue Test Utils

---

## File Map

- Modify: `frontend/src/views/NewsFeedView.vue`
- Modify: `frontend/src/views/NewsFeedView.test.ts`
- Modify: `frontend/src/components/news/NewsCard.vue`
- Modify: `frontend/src/components/news/NewsCard.test.ts`
- Modify: `docs/code-change-log.md`

## Chunk 1: Test-First News Feed Refinement

- [ ] **Step 1: Update NewsFeed/NewsCard tests with refined shell anchors**
- [ ] **Step 2: Run targeted tests and verify failure**

Run:

```bash
npm --prefix frontend run test -- --run src/components/news/NewsCard.test.ts src/views/NewsFeedView.test.ts
```

- [ ] **Step 3: Implement the minimal filter-bar and stream-card refinement**
- [ ] **Step 4: Re-run targeted tests and verify pass**

## Chunk 2: Verification And Documentation

- [ ] **Step 5: Run frontend build**
- [ ] **Step 6: Update `docs/code-change-log.md`**
- [ ] **Step 7: Request review and fix Important/Critical issues**
