# Supporting Stories Horizontal Layout Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert supporting stories into compact horizontal cards while preserving the existing editorial flow.

**Architecture:** Keep `StoryStrip.vue` as the grid container and isolate the layout change inside the `supporting` variant of `NewsCard.vue`. Add a targeted component test that proves the new supporting-card structure exists before implementation.

**Tech Stack:** Vue 3, Vite, Vitest, Vue Test Utils

---

## Chunk 1: Test And Supporting Card Structure

### Task 1: Add a failing component test

**Files:**
- Create: `frontend/src/components/news/StoryStrip.test.ts`
- Modify: `frontend/src/components/news/StoryStrip.vue`
- Modify: `frontend/src/components/news/NewsCard.vue`

- [ ] Step 1: Write a failing test that mounts `StoryStrip` and asserts supporting cards render a dedicated horizontal body wrapper.
- [ ] Step 2: Run `npm --prefix frontend run test -- --run src/components/news/StoryStrip.test.ts` and confirm it fails because the wrapper does not exist yet.
- [ ] Step 3: Implement the minimal template changes in `NewsCard.vue` for `variant="supporting"`.
- [ ] Step 4: Update `StoryStrip.vue` breakpoints to 3/2/1 columns.
- [ ] Step 5: Re-run `npm --prefix frontend run test -- --run src/components/news/StoryStrip.test.ts` and confirm it passes.

## Chunk 2: Verification And Record

### Task 2: Verify and document

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] Step 1: Run `npm --prefix frontend run build`.
- [ ] Step 2: Update `docs/code-change-log.md` with the supporting stories layout change, verification commands, and remaining responsive risk.
