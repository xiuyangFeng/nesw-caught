# X Monitor Refresh Cooldown Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 3-hour cooldown to account refreshes, keep only `MiniMax_AI` in the monitored account list, and surface cooldown state to the UI.

**Architecture:** Reuse `x_source_health.last_success_at` as the cooldown anchor, extend the refresh response with skipped/next-refresh metadata, and update the view/store to render the cooldown window. Keep keyword search unchanged and preserve provider-returned original URLs only.

**Tech Stack:** Python, FastAPI, SQLAlchemy, pytest, Vue 3, Pinia, Vitest

---

## Chunk 1: Lock cooldown behavior in tests

### Task 1: Add failing backend and frontend tests

**Files:**
- Modify: `backend/tests/test_x_monitor.py`
- Modify: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 1: Add a backend test for cooldown skip**
- [ ] **Step 2: Add a backend test for refresh response metadata**
- [ ] **Step 3: Add a frontend test for next refresh messaging**
- [ ] **Step 4: Run targeted tests to verify they fail**

## Chunk 2: Implement cooldown behavior

### Task 2: Update backend refresh logic and response schema

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/x_monitor.py`
- Modify: `backend/app/schemas/x_monitor.py`
- Modify: `backend/app/api/routes/x_monitor.py`
- Modify: `backend/data/x_monitor_accounts.example.json`

- [ ] **Step 1: Add the cooldown config default**
- [ ] **Step 2: Return skipped/next-refresh metadata from refresh**
- [ ] **Step 3: Change the sample account list to `MiniMax_AI` only**
- [ ] **Step 4: Run targeted backend tests**

### Task 3: Update the frontend cooldown display

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/stores/xMonitorStore.ts`
- Modify: `frontend/src/views/XMonitorView.vue`

- [ ] **Step 1: Extend refresh result typing**
- [ ] **Step 2: Add mock cooldown state**
- [ ] **Step 3: Render next refresh / cooldown skip state**
- [ ] **Step 4: Run targeted frontend test**

## Chunk 3: Verify and smoke test

### Task 4: Run verification and real provider smoke test

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run `conda run -n news-caught pytest backend/tests -q`**
- [ ] **Step 2: Run `npm --prefix frontend run build`**
- [ ] **Step 3: Run a real `MiniMax_AI` account smoke test**
- [ ] **Step 4: Update `docs/code-change-log.md`**
