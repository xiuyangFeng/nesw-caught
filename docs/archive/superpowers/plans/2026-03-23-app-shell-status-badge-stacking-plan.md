# App Shell Status Badge Stacking Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent long status badges in the `AppShell` sidebar card from squeezing the label column and causing visible misalignment.

**Architecture:** Keep existing status data and color semantics, but replace the header-row layout with a shared vertical stack and a full-width status badge style inside the sidebar card. Verify the stacking contract via targeted component tests before implementation.

**Tech Stack:** Vue 3, Vue Test Utils, Vitest, Tailwind utilities, Vite build

---

## Chunk 1: TDD For Stacked Badge Layout

### Task 1: Add a failing test for stacked status units

**Files:**
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Modify: `frontend/src/components/layout/AppShell.vue`

- [ ] **Step 1: Write the failing test**

Assert that:
- the shell status unit uses a shared stacked layout marker instead of the two-column grid marker
- the market-worker unit uses the same stacked marker
- the market-worker badge is rendered with a full-width constraint

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: FAIL because the current markup still uses the older grid-row structure and does not mark the full-width badge variant.

- [ ] **Step 3: Implement the minimal template update**

Convert the two status units to the shared stacked layout and make the card badge full-width.

- [ ] **Step 4: Re-run the focused test**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: PASS.

## Chunk 2: Verification And Recordkeeping

### Task 2: Update records and run final verification

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log**

Record that the shell status card now stacks labels and long badges to avoid squeezing in the sidebar.

- [ ] **Step 2: Run targeted test verification**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: PASS.

- [ ] **Step 3: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS.
