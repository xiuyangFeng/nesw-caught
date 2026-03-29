# News Discovery Homepage Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refocus the product homepage on a compact latest-events discovery flow instead of a multi-module dashboard.

**Architecture:** Reuse the existing news feed/event infrastructure rather than introducing a second homepage data model. Move root navigation to the news-discovery experience, compress the event-row presentation, and demote old dashboard-first framing so supporting modules reinforce event discovery instead of competing with it.

**Tech Stack:** Vue 3, Pinia, Vue Router, Vite, Vitest, FastAPI backend (contract preserved unless required)

---

## File Map

- Modify: `frontend/src/router/index.ts`
  - Make the root route land on the event discovery page.
- Modify: `frontend/src/components/news/EventFeedCard.vue`
  - Compress event row height and surface compact metadata.
- Modify: `frontend/src/components/news/NewsCard.vue`
  - Keep supporting stream cards visually subordinate to the event list.
- Modify: `frontend/src/views/NewsFeedView.vue`
  - Reframe the page as the compact homepage event stream and reduce visual height.
- Modify: `frontend/src/views/DashboardView.vue`
  - Demote dashboard framing if it remains accessible.
- Modify: `frontend/src/components/layout/AppShell.vue`
  - Keep route/event refresh logic compatible with the new root/default behavior.
- Modify: `frontend/src/components/news/EventFeedCard.test.ts`
  - Lock the compact event-row rendering contract.
- Modify: `frontend/src/router/index.test.ts`
  - Verify root navigation behavior directly against the router.
- Modify: `frontend/src/views/NewsFeedView.test.ts`
  - Add tests for event-first compact rendering and root-oriented framing.
- Modify: `frontend/src/components/layout/AppShell.test.ts`
  - Add or adjust route/default-load expectations and guard feed refresh logic.
- Modify: `docs/code-change-log.md`
  - Record the completed change unit.

## Chunk 1: Default Route And Shell Safety

### Task 1: Redirect root navigation to the news discovery experience

**Files:**
- Modify: `frontend/src/router/index.ts`
- Test: `frontend/src/router/index.test.ts`
- Test: `frontend/src/components/layout/AppShell.test.ts`

- [ ] **Step 1: Write the failing test**

Add:

- a router-level test proving `/` resolves to the news discovery route
- a shell test covering any assumptions affected by the new default route and feed refresh safety

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/router/index.test.ts src/components/layout/AppShell.test.ts`
Expected: FAIL because root still redirects to dashboard and/or the shell still assumes dashboard-first flow or unsafe feed-query state.

- [ ] **Step 3: Write minimal implementation**

Update router defaults and shell route handling so root navigation lands on the news discovery page without relying on undefined feed query state.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/router/index.test.ts src/components/layout/AppShell.test.ts`
Expected: PASS

### Task 2: Align shell navigation language with news discovery priority

**Files:**
- Modify: `frontend/src/components/layout/AppShell.vue`
- Test: `frontend/src/components/layout/AppShell.test.ts`

- [ ] **Step 1: Write the failing test**

Add expectations that the shell navigation and terminal framing present news discovery as the primary module rather than a dashboard-first control room.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: FAIL because nav ordering or shell copy still privileges dashboard-first framing.

- [ ] **Step 3: Write minimal implementation**

Adjust nav order, labels, and shell framing so event discovery is the leading mental model while preserving access to dashboard, watchlist, and X Radar.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: PASS

## Chunk 2: Compact Event-First Homepage

### Task 3: Convert the news feed surface into the compact homepage event stream

**Files:**
- Modify: `frontend/src/components/news/EventFeedCard.vue`
- Modify: `frontend/src/components/news/NewsCard.vue`
- Modify: `frontend/src/views/NewsFeedView.vue`
- Test: `frontend/src/components/news/EventFeedCard.test.ts`
- Test: `frontend/src/views/NewsFeedView.test.ts`

- [ ] **Step 1: Write the failing test**

Add tests that lock in:

- event stream is presented as the primary homepage layer
- compact event rows render the approved metadata contract
- compact row styling/framing hooks exist
- large showcase-style summary emphasis is reduced

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts`
Expected: FAIL because current rendering still uses the older, larger event-card framing and “signal desk” presentation.

- [ ] **Step 3: Write minimal implementation**

Refactor `EventFeedCard`, `NewsCard`, and `NewsFeedView` so the homepage presents a compact high-density event-first design while preserving existing data loading behavior.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts`
Expected: PASS

## Chunk 3: Demote Dashboard Framing

### Task 4: Make the remaining dashboard surface secondary instead of primary

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`
- Test: `frontend/src/views/DashboardView.test.ts`

- [ ] **Step 1: Write the failing test**

Add or update tests to reflect that dashboard is no longer the primary landing experience and its copy/entry points no longer compete with latest-event discovery.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`
Expected: FAIL because the existing dashboard still uses primary control-room framing.

- [ ] **Step 3: Write minimal implementation**

Reduce dashboard-first emphasis and align its language with a secondary overview role.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- --run src/views/DashboardView.test.ts`
Expected: PASS

## Chunk 4: Verification And Recordkeeping

### Task 5: Verify the homepage refactor and record the change

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run targeted frontend verification**

Run:
- `npm --prefix frontend run test -- --run src/router/index.test.ts src/components/layout/AppShell.test.ts src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts src/views/DashboardView.test.ts`
- `npm --prefix frontend run build`

Expected: targeted tests pass and frontend production build succeeds.

- [ ] **Step 2: Run broader regression spot-check**

Run: `npm --prefix frontend run test -- --run`
Expected: note whether remaining failures are introduced by this change or are pre-existing baseline issues.

- [ ] **Step 3: Update change log**

Append a new entry to `docs/code-change-log.md` describing:

- route/homepage shift to latest events
- compact event density change
- verification commands and outcomes
- known residual risks or pre-existing failures if any remain

- [ ] **Step 4: Commit**

- [ ] **Step 4: Request code review**

Run the repository-required review step against the implemented change set before final commit/push and address any findings.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/index.ts \
  frontend/src/router/index.test.ts \
  frontend/src/components/layout/AppShell.vue \
  frontend/src/components/layout/AppShell.test.ts \
  frontend/src/components/news/EventFeedCard.vue \
  frontend/src/components/news/EventFeedCard.test.ts \
  frontend/src/components/news/NewsCard.vue \
  frontend/src/views/NewsFeedView.vue \
  frontend/src/views/NewsFeedView.test.ts \
  frontend/src/views/DashboardView.vue \
  frontend/src/views/DashboardView.test.ts \
  docs/code-change-log.md \
  docs/superpowers/specs/2026-03-29-news-discovery-homepage-design.md \
  docs/superpowers/plans/2026-03-29-news-discovery-homepage-plan.md
git commit -m "feat: refocus homepage on latest event discovery"
```

- [ ] **Step 6: Finish development branch checks**

Use the repository closing workflow to confirm verification status, branch cleanliness, and delivery readiness before push.

## Notes

- Preserve backend contracts unless a compact event row absolutely requires new metadata.
- Do not add AI ranking or filtering logic in this implementation.
- Treat unrelated backend baseline failures as existing debt unless this work directly changes those paths.
