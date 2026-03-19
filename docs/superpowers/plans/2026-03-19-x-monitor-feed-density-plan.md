# X Monitor Feed Density Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the X Monitor post feed denser by switching the right panel to a fixed-height, internally scrollable list layout with a status-style summary block.

**Architecture:** Keep all behavior inside `frontend/src/views/XMonitorView.vue` and its existing test file. Add a small set of computed summary strings, update the feed markup to introduce a summary header plus compact list items, and adjust scoped CSS to constrain feed height on desktop while falling back to normal flow on mobile.

**Tech Stack:** Vue 3, Vitest, Vue Test Utils, scoped CSS

---

## Chunk 1: Test-First Feed Density Update

### Task 1: Expand the view test for the new summary and compact feed structure

**Files:**
- Modify: `frontend/src/views/XMonitorView.test.ts`
- Test: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 1: Write the failing test assertions**

Add assertions for:
- summary text containing the tracked post count
- the compact summary secondary line still containing throttling/cooldown info
- the new compact feed container and list-item class names

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: FAIL because the new summary text or structural selectors do not exist yet.

### Task 2: Implement the compact feed markup and styles

**Files:**
- Modify: `frontend/src/views/XMonitorView.vue`
- Test: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 3: Add minimal computed summary text**

Create computed values for:
- tracked post count summary
- condensed refresh/status text

- [ ] **Step 4: Replace the large-card feed markup**

Update the “账号监控帖子流” section to:
- render the summary block above the list
- switch each post from the large card treatment to a list-style item layout
- keep existing data fields and links intact

- [ ] **Step 5: Update scoped CSS**

Implement:
- desktop-only max height/internal scroll for the feed list
- compact list-item spacing, smaller body text, lighter borders/shadows
- responsive fallback that removes forced height on narrow screens

- [ ] **Step 6: Re-run the targeted view test**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: PASS

## Chunk 2: Verification and Documentation

### Task 3: Run broader frontend verification

**Files:**
- Modify: `frontend/src/views/XMonitorView.vue`
- Modify: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 7: Build the frontend**

Run: `npm --prefix frontend run build`
Expected: PASS

### Task 4: Record the change

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 8: Append the code change log entry**

Document:
- fixed-height/internal-scroll feed
- compact list-style post items
- new summary copy
- validation commands run

- [ ] **Step 9: Re-check working tree for only intended changes**

Run: `git status --short`
Expected: existing unrelated changes remain untouched; only intended X Monitor view/test/doc changes are newly added or modified.
