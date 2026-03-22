# App Shell Terminal Refinement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the shared app shell into a stronger terminal-style control column with a compact global status rail, without changing routing or data behavior.

**Architecture:** Keep `AppShell` as the sole shell owner and confine changes to shell markup, copy, and Tailwind classes. Lock the new behavior with `AppShell` component tests first, then update the shell implementation minimally to satisfy the tests and preserve current bootstrap/SSE wiring.

**Tech Stack:** Vue 3, Vue Router, Pinia stores, Tailwind CSS, Vitest, Vue Test Utils

---

## File Map

- Modify: `frontend/src/components/layout/AppShell.vue`
  - Refine sidebar hierarchy, add shell-level status rail, tighten status module wording and active nav styling
- Modify: `frontend/src/components/layout/AppShell.test.ts`
  - Add assertions for the new shell rail and updated shell copy/markers
- Modify: `docs/code-change-log.md`
  - Record the implementation work and verification evidence after code changes

## Chunk 1: AppShell Test-First Shell Refinement

### Task 1: Lock the new shell landmarks in tests

**Files:**
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Test: `frontend/src/components/layout/AppShell.test.ts`

- [ ] **Step 1: Write the failing test assertions for the refined shell**

Add assertions for:
- new shell status rail landmark
- refined desk note wording
- active navigation marker still present with route index/module text
- compact system status wording

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts
```

Expected:
- FAIL because the new shell rail landmark and updated wording do not exist yet

### Task 2: Implement the minimal shell refinement

**Files:**
- Modify: `frontend/src/components/layout/AppShell.vue`
- Test: `frontend/src/components/layout/AppShell.test.ts`

- [ ] **Step 3: Update the shell template and classes**

Implement:
- compact shell status rail above routed content
- stronger active navigation styling using the existing route/index model
- tighter system desk note and bottom status module copy
- keep all bootstrap and SSE behavior unchanged

- [ ] **Step 4: Run the targeted test to verify it passes**

Run:

```bash
npm --prefix frontend run test -- --run src/components/layout/AppShell.test.ts
```

Expected:
- PASS with all `AppShell` tests green

- [ ] **Step 5: Refactor only if needed while keeping tests green**

Allowed:
- extract small class helpers
- tighten label strings

Not allowed:
- route changes
- store logic changes

## Chunk 2: Verification And Documentation

### Task 3: Verify shell integration and record the change

**Files:**
- Modify: `docs/code-change-log.md`
- Test: `frontend/src/components/layout/AppShell.test.ts`

- [ ] **Step 6: Run production build verification**

Run:

```bash
npm --prefix frontend run build
```

Expected:
- PASS with successful type-check and Vite build

- [ ] **Step 7: Update the code change log with factual implementation details**

Record:
- shell visual changes
- impacted files
- verification commands and results
- residual risks about page-level follow-on refinement

- [ ] **Step 8: Request code review for the finished AppShell task**

Review against:
- `docs/superpowers/specs/2026-03-22-app-shell-terminal-refinement-design.md`
- this implementation plan

- [ ] **Step 9: Address any Important or Critical review issues and re-verify**

Re-run the same relevant verification commands after fixes.
