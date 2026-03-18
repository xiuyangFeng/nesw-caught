# News Feed Terminal Refinement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the News Feed visual language into a colder trading-terminal style and compress the lead story into a compact horizontal reading card.

**Architecture:** Keep the existing editorial grouping and route flow unchanged while updating global design tokens, the lead-story component structure, and the News Feed layout rhythm. All behavior changes are locked with frontend tests before production code edits.

**Tech Stack:** Vue 3, TypeScript, Vitest, Vite, scoped CSS

---

## Chunk 1: Test Coverage For Lead Story Structure

### Task 1: Add a failing test for the compact lead-story structure

**Files:**
- Create: `frontend/src/components/news/LeadStoryCard.test.ts`
- Modify: `frontend/src/components/news/LeadStoryCard.vue`
- Test: `frontend/src/components/news/LeadStoryCard.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it('renders the compact terminal lead-story structure', () => {
  const wrapper = renderLeadStory();
  expect(wrapper.get('[data-role="lead-label"]').text()).toContain('Primary Signal');
  expect(wrapper.get('[data-role="lead-title"]').exists()).toBe(true);
  expect(wrapper.get('[data-role="lead-summary"]').exists()).toBe(true);
  expect(wrapper.get('[data-role="lead-meta"]').exists()).toBe(true);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/news/LeadStoryCard.test.ts`
Expected: FAIL because the new `data-role` hooks do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add the `data-role` hooks and compact structure in `LeadStoryCard.vue` without changing click behavior.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/components/news/LeadStoryCard.test.ts`
Expected: PASS

## Chunk 2: Terminal Palette And Layout Refinement

### Task 2: Update global tokens and lead-story styling

**Files:**
- Modify: `frontend/src/assets/main.css`
- Modify: `frontend/src/components/news/LeadStoryCard.vue`
- Modify: `frontend/src/views/NewsFeedView.vue`
- Test: `frontend/src/components/news/LeadStoryCard.test.ts`
- Test: `frontend/src/views/NewsFeedView.test.ts`

- [ ] **Step 1: Adjust global token values**

Update `:root` colors to:

```css
--bg: #050a12;
--bg-elevated: #0a111b;
--panel: rgba(10, 16, 26, 0.94);
--panel-strong: #0f1724;
--accent: #53c2ff;
--accent-soft: rgba(83, 194, 255, 0.12);
--system: #7dd3fc;
```

and remove the bright warm glow from `--bg-accent`.

- [ ] **Step 2: Refine lead-story card layout**

Implement:

```css
.lead-story {
  gap: 12px;
  padding: 24px 26px;
}

.lead-story__body {
  display: grid;
  gap: 10px;
}

.lead-story h2 {
  max-width: none;
  font-size: clamp(26px, 2.4vw, 36px);
}
```

plus a horizontal meta strip that wraps cleanly on smaller widths.

- [ ] **Step 3: Tighten News Feed section rhythm**

Reduce oversized spacing in `NewsFeedView.vue`, keep `Primary Signal`, `Signal Queue`, and `News Stream` ordering intact, and make the header secondary to the card itself.

- [ ] **Step 4: Run focused tests**

Run: `npm --prefix frontend run test -- --run src/components/news/LeadStoryCard.test.ts src/views/NewsFeedView.test.ts`
Expected: PASS

## Chunk 3: Verification And Project Record

### Task 3: Verify build output and update records

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update code change log**

Add a new top entry describing:

- cold blue-gray terminal palette refinement
- compact horizontal lead-story card
- affected frontend files
- verification commands run

- [ ] **Step 2: Run production build**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 3: Final status check**

Run: `git status --short`
Expected: only the intended doc, test, and frontend file changes appear.
