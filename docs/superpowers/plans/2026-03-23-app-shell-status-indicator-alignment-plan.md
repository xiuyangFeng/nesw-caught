# App Shell Status Indicator Alignment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `AppShell` system-status card so the left-side status labels stay aligned even when the right-side badges use longer text.

**Architecture:** Keep the existing `AppShell` data flow and badge semantics, but replace the two status header rows with a shared two-column grid layout. Verify the layout contract through a targeted component test before changing production markup.

**Tech Stack:** Vue 3, Vue Test Utils, Vitest, Tailwind utility classes, Vite build

---

## Chunk 1: TDD For Alignment Contract

### Task 1: Add a failing test for unified status-row layout

**Files:**
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Modify: `frontend/src/components/layout/AppShell.vue`

- [ ] **Step 1: Write the failing test**

Assert that:
- the `System Status` header row uses the new shared grid layout marker
- the `Market worker` header row uses the same shared grid layout marker
- long worker text still renders in the card

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: FAIL because the current markup still uses the older `flex justify-between` layout and does not expose the shared row marker.

- [ ] **Step 3: Implement the minimal template update**

Change the two status rows in `AppShell.vue` to the shared grid layout and keep the rest of the card intact.

- [ ] **Step 4: Re-run the focused test**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: PASS.

## Chunk 2: Verification And Recordkeeping

### Task 2: Update records and run final verification

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log**

Record that the shell status card now uses a stable grid-based status-row layout to keep indicator labels aligned.

- [ ] **Step 2: Run targeted test verification**

Run: `npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts`
Expected: PASS.

- [ ] **Step 3: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS.
