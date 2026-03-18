# News Feed Unified Horizontal List Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the editorially-ranked News Feed layout with a single original-order horizontal card list.

**Architecture:** Keep the existing store loading and detail hydration, but stop grouping items into lead/supporting/stream buckets. Render one list in input order and unify the card component styling into a compact horizontal layout.

**Tech Stack:** Vue 3, TypeScript, Vitest, scoped CSS, Vite

---

## Chunk 1: Lock Original Order And Remove Lead Story

### Task 1: Add failing view tests for unified list behavior

**Files:**
- Modify: `frontend/src/views/NewsFeedView.test.ts`
- Modify: `frontend/src/views/NewsFeedView.vue`
- Test: `frontend/src/views/NewsFeedView.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it('renders a unified list in original order without Primary Signal', () => {
  const wrapper = mount(NewsFeedView);
  expect(wrapper.text()).not.toContain('Primary Signal');
  const titles = wrapper.findAll('[data-role="news-card-title"]').map((node) => node.text());
  expect(titles).toEqual([
    'NVIDIA rallies as AI capex estimates move higher',
    'TSMC supply chain remains in focus',
  ]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts`
Expected: FAIL because the page still renders `Primary Signal` and does not expose a unified ordered list.

- [ ] **Step 3: Write minimal implementation**

Remove `groupEditorialStories` usage from the view and render one list in input order.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts`
Expected: PASS

## Chunk 2: Unify Card Layout Into Horizontal Terminal Cards

### Task 2: Add failing component test and implement compact horizontal card styling

**Files:**
- Modify: `frontend/src/components/news/NewsCard.vue`
- Create or Modify: `frontend/src/components/news/NewsCard.test.ts`
- Test: `frontend/src/components/news/NewsCard.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it('renders a horizontal news card layout with body and meta columns', () => {
  const wrapper = mount(NewsCard, { props: { entry: makeEntry(), variant: 'stream' } });
  expect(wrapper.find('.news-card__body').exists()).toBe(true);
  expect(wrapper.find('.news-card__meta').exists()).toBe(true);
  expect(wrapper.find('[data-role="news-card-title"]').exists()).toBe(true);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/news/NewsCard.test.ts`
Expected: FAIL because the shared horizontal body/meta structure does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Use one shared horizontal structure for homepage cards:

```vue
<div class="news-card__body">
  <div class="news-card__copy">...</div>
  <div class="news-card__meta">...</div>
</div>
```

with summary clamped to 2 lines.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/components/news/NewsCard.test.ts`
Expected: PASS

## Chunk 3: Verification And Records

### Task 3: Update records and verify production build

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log**

Record the removal of `Primary Signal`, original-order list rendering, and unified horizontal cards.

- [ ] **Step 2: Run focused verification**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/news/NewsCard.test.ts`
Expected: PASS

- [ ] **Step 3: Run production build**

Run: `npm --prefix frontend run build`
Expected: PASS
