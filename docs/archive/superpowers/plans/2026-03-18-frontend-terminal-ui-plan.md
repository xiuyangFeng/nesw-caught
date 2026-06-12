# Frontend Terminal UI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-skin the frontend into a darker terminal-style financial workstation by updating global tokens, shell/navigation, shared surfaces, and the News Feed and Dashboard presentation without changing routes or API behavior.

**Architecture:** Keep the existing Vue page/component structure and data flow intact, but replace the visual system from the top down. First lock in shared dark-theme tokens and shell styling, then update reusable cards/banners/metrics, then restyle News Feed and Dashboard so they inherit the same signal-color semantics and density rules. Verification relies on targeted component tests plus the full frontend test suite and build.

**Tech Stack:** Vue 3, TypeScript, Pinia, Vue Router, Vitest, Vite

---

## Chunk 1: Shared Terminal Visual System

### Task 1: Add failing tests for the new shell and shared component semantics

**Files:**
- Create: `frontend/src/components/layout/AppShell.test.ts`

- [ ] **Step 1: Write the failing test**

Add tests that assert the new global shell semantics exist:
- the sidebar renders a system-header block, primary nav, and system-status module
- the active nav link exposes a terminal-style active indicator class/data attribute
- the shell still renders a `RouterView` content mount after the shell markup changes

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: FAIL because the shell has not been updated to the new terminal structure yet.

- [ ] **Step 3: Write minimal implementation**

Update the shell markup in `frontend/src/components/layout/AppShell.vue` only enough to satisfy the new structural expectations while keeping routing and store bootstrapping behavior unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: PASS

### Task 2: Replace global tokens and shared surface primitives

**Files:**
- Modify: `frontend/src/assets/main.css`
- Modify: `frontend/src/components/common/SectionCard.vue`
- Modify: `frontend/src/components/common/StatusBanner.vue`
- Modify: `frontend/src/components/dashboard/HeroMetrics.vue`
- Create: `frontend/src/components/common/SectionCard.test.ts`
- Create: `frontend/src/components/common/StatusBanner.test.ts`
- Create: `frontend/src/components/dashboard/HeroMetrics.test.ts`

- [ ] **Step 1: Write the failing test**

Add dedicated component tests so shared surfaces require the updated structure/class hooks needed by the terminal theme:
- section cards expose eyebrow/title grouping
- hero metrics expose semantic tone hooks
- status banners preserve tone-specific semantics after the dark-theme refactor

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/common/SectionCard.test.ts src/components/common/StatusBanner.test.ts src/components/dashboard/HeroMetrics.test.ts`
Expected: FAIL because the shared primitives do not yet expose the new terminal-style structure.

- [ ] **Step 3: Write minimal implementation**

Implement the shared dark-theme tokens and update the shared primitives to use:
- dark surfaces and cool borders
- orange focus/editorial cues
- blue system-state cues
- tighter spacing and reduced card radii

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/components/common/SectionCard.test.ts src/components/common/StatusBanner.test.ts src/components/dashboard/HeroMetrics.test.ts`
Expected: PASS

## Chunk 2: Page-Level Terminal Restyling

### Task 3: Add failing tests for News Feed terminal presentation

**Files:**
- Modify: `frontend/src/components/news/StoryStrip.test.ts`
- Create: `frontend/src/views/NewsFeedView.test.ts`
- Modify: `frontend/src/views/NewsFeedView.vue`
- Modify: `frontend/src/components/news/LeadStoryCard.vue`
- Modify: `frontend/src/components/news/NewsCard.vue`
- Modify: `frontend/src/components/news/StoryStrip.vue`

- [ ] **Step 1: Write the failing test**

Add tests that assert:
- the News Feed header exposes terminal-style edition/system labels
- the supporting-story strip renders the updated section heading and supporting card structure
- the stream section keeps navigation behavior intact after copy/class changes

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/news/StoryStrip.test.ts`
Expected: FAIL because the page and supporting news components still use the pre-terminal wording/structure.

- [ ] **Step 3: Write minimal implementation**

Restyle the News Feed around the existing editorial hierarchy:
- darker lead story treatment with orange editorial focus
- blue system/filter affordances
- tighter supporting and stream cards
- wrapped dark filter bar with preserved functionality

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/news/StoryStrip.test.ts`
Expected: PASS

### Task 4: Add failing tests for Dashboard terminal presentation

**Files:**
- Create: `frontend/src/views/DashboardView.test.ts`
- Modify: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: Write the failing test**

Add tests that assert:
- the dashboard exposes a terminal-style summary label/header treatment
- the hero metric cards render the tightened workstation wording/structure
- the latest news and abnormal movers sections still render data under the new panel layout
- shared `HeroMetrics` semantics remain intact when rendered through the dashboard

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`
Expected: FAIL because the current dashboard still uses the brighter summary-page treatment.

- [ ] **Step 3: Write minimal implementation**

Restyle `frontend/src/views/DashboardView.vue` to feel like the market control room:
- tighter header and status treatment
- denser hero metrics layout
- darker movement/news modules that share the same terminal semantics as News Feed

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`
Expected: PASS

## Chunk 3: Verification, Documentation, and Delivery

### Task 5: Run full verification and update project records

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update change log entry**

Add a new top entry that records:
- terminal-style frontend visual redesign
- affected shared components and primary pages
- test/build verification results

- [ ] **Step 2: Run full frontend tests**

Run: `npm --prefix frontend run test -- --run`
Expected: PASS

- [ ] **Step 3: Run frontend build verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Spot-check requirements against the spec**

Verify that the implementation:
- keeps routes and API behavior unchanged
- uses orange for editorial focus and blue for system-state emphasis
- preserves clear keyboard-visible focus states and readable dark-theme contrast
- collapses the shell cleanly at `1100px`

- [ ] **Step 5: Run a browser-level responsive check**

Use Playwright to verify at minimum:
- dashboard/news multi-column sections collapse cleanly around `1320px`
- desktop shell remains two-column above `1100px`
- shell collapses below `1100px`
- supporting-story/news grids collapse cleanly around `768px`
- News Feed filter bar wraps without horizontal overflow
- focus/active states remain visible on dark surfaces

- [ ] **Step 6: Commit**

```bash
git add frontend docs/superpowers/specs/2026-03-18-frontend-terminal-ui-design.md docs/superpowers/plans/2026-03-18-frontend-terminal-ui-plan.md docs/code-change-log.md
git commit -m "重构前端终端式视觉系统"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-18-frontend-terminal-ui-plan.md`. Ready to execute?
