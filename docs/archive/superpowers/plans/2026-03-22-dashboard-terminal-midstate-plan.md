# Dashboard Terminal Midstate Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine Dashboard visuals into the agreed terminal midpoint while preserving existing layout responsibilities and data behavior.

**Architecture:** Keep `DashboardView` as the page owner and make small presentational refinements in `HeroMetrics` and `TopicBoard` to support the stronger control-room style. Use TDD by updating focused component/page tests before changing implementation.

**Tech Stack:** Vue 3, Tailwind CSS, Vitest, Vue Test Utils

---

## File Map

- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/views/DashboardView.test.ts`
- Modify: `frontend/src/components/dashboard/HeroMetrics.vue`
- Modify: `frontend/src/components/dashboard/HeroMetrics.test.ts`
- Modify: `frontend/src/components/dashboard/TopicBoard.vue`
- Modify: `frontend/src/components/dashboard/TopicBoard.test.ts`
- Modify: `docs/code-change-log.md`

## Chunk 1: Test-First Dashboard Refinement

### Task 1: Update tests for the new control-room anchors

- [ ] **Step 1: Write failing tests for the refined Dashboard/HeroMetrics/TopicBoard anchors**
- [ ] **Step 2: Run targeted tests and verify failure**

Run:

```bash
npm --prefix frontend run test -- --run src/components/dashboard/HeroMetrics.test.ts src/components/dashboard/TopicBoard.test.ts src/views/DashboardView.test.ts
```

Expected:
- FAIL on new visual-anchor assertions

### Task 2: Implement the minimal visual refinement

- [ ] **Step 3: Refine HeroMetrics into tighter shell modules**
- [ ] **Step 4: Refine TopicBoard hierarchy for stronger signal framing**
- [ ] **Step 5: Refine Dashboard movers/feed presentation while preserving current structure**
- [ ] **Step 6: Re-run targeted tests and verify pass**

## Chunk 2: Verification And Documentation

### Task 3: Full verification and log

- [ ] **Step 7: Run frontend build**

```bash
npm --prefix frontend run build
```

- [ ] **Step 8: Update `docs/code-change-log.md` with implementation facts and verification**
- [ ] **Step 9: Request code review and fix any Important/Critical findings**
