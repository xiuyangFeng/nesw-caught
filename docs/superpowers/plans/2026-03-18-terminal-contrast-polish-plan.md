# Terminal Contrast Polish Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace low-contrast pale surfaces with readable dark terminal surfaces and add a local `scripts/start-server.sh` wrapper for visual companion use.

**Architecture:** Keep the current cold blue-gray system but standardize dark surface tokens and apply them to the main problem areas called out by the user. Lock the component surface changes with focused tests before editing production styles, and add a repository-level shell wrapper that forwards to the brainstorming skill script.

**Tech Stack:** Vue 3, TypeScript, Vitest, scoped CSS, shell script

---

## Chunk 1: Test Surface Hooks

### Task 1: Add failing tests for terminal-surface wrappers

**Files:**
- Create: `frontend/src/components/watchlist/WatchlistTable.test.ts`
- Create: `frontend/src/components/dashboard/TopicBoard.test.ts`
- Modify: `frontend/src/components/watchlist/WatchlistTable.vue`
- Modify: `frontend/src/components/dashboard/TopicBoard.vue`

- [ ] **Step 1: Write the failing tests**

```ts
expect(wrapper.find('[data-surface="terminal-table"]').exists()).toBe(true);
expect(wrapper.find('[data-surface="terminal-card"]').exists()).toBe(true);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts`
Expected: FAIL because the new terminal surface hooks do not exist yet.

- [ ] **Step 3: Add minimal implementation**

Add the `data-surface` hooks while keeping component behavior unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts`
Expected: PASS

## Chunk 2: Contrast And Surface Implementation

### Task 2: Apply dark terminal surfaces across the affected pages

**Files:**
- Modify: `frontend/src/assets/main.css`
- Modify: `frontend/src/components/common/SectionCard.vue`
- Modify: `frontend/src/components/watchlist/WatchlistTable.vue`
- Modify: `frontend/src/components/dashboard/TopicBoard.vue`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/XMonitorView.vue`
- Modify: `frontend/src/views/TopicDetailView.vue`
- Modify: `frontend/src/views/NewsDetailView.vue`

- [ ] **Step 1: Add stronger surface tokens**

Introduce tokens like:

```css
--panel-stronger: #0d1623;
--panel-soft: rgba(15, 24, 37, 0.9);
--field-bg: rgba(9, 16, 26, 0.96);
--text-faint: #93a7bf;
```

- [ ] **Step 2: Replace pale backgrounds**

Remove `rgba(255, 255, 255, 0.34~0.9)` and `#fffdf8` from the affected components/views and switch them to the dark tokens.

- [ ] **Step 3: Tighten text contrast**

Use brighter text for titles and clearer gray-blue for metadata and summaries so text remains readable over dark surfaces.

## Chunk 3: Local Wrapper Script

### Task 3: Add repository-level start-server wrapper

**Files:**
- Create: `scripts/start-server.sh`

- [ ] **Step 1: Add the shell wrapper**

Implement a small forwarding script that:

- resolves the skill script path
- checks that it exists and is executable
- forwards all user arguments

- [ ] **Step 2: Make it executable**

Run: `chmod +x scripts/start-server.sh`
Expected: script is runnable from the repo root

## Chunk 4: Verification And Records

### Task 4: Update records and verify build

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log**

Record:

- terminal contrast polish across table/card/filter surfaces
- improved text readability
- local `scripts/start-server.sh` wrapper

- [ ] **Step 2: Run focused tests**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/WatchlistTable.test.ts src/components/dashboard/TopicBoard.test.ts`
Expected: PASS

- [ ] **Step 3: Run production build**

Run: `npm --prefix frontend run build`
Expected: PASS
