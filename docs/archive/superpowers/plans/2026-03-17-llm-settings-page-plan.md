# LLM Settings Page Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single active LLM settings page that reads and updates the existing backend config safely, including preserving the current API key when the user edits other fields without re-entering the key.

**Architecture:** Extend the backend config upsert semantics so empty API key updates preserve the existing stored key, then add a dedicated frontend LLM settings page with its own store, route, navigation entry, and tests. Rewire the news detail page to read global LLM config from the dedicated store instead of the news store.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Pinia, Vitest-ready frontend, pytest backend tests

---

## Chunk 1: Backend Config Update Semantics

### Task 1: Add failing backend tests for preserving existing API key

**Files:**
- Modify: `backend/tests/test_llm_config.py`

- [ ] **Step 1: Write the failing preserve-key test**

Cover:
- create a config with a non-empty key
- update the same config with changed `model_name` and empty `api_key`
- assert `api_key_set` remains true and later LLM analysis still sees the stored key

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_llm_config.py -q`
Expected: FAIL because the current upsert clears the key on empty submission.

### Task 2: Implement preserve-key behavior in backend config upsert

**Files:**
- Modify: `backend/app/schemas/llm.py`
- Modify: `backend/app/repositories/llm_provider_config_repository.py`
- Optionally modify: `backend/app/api/routes/llm.py`

- [ ] **Step 1: Make request schema accept empty or omitted API key on update**
- [ ] **Step 2: Preserve existing key when updating and no new key is provided**
- [ ] **Step 3: Keep API key required on first-time create**
- [ ] **Step 4: Run focused backend tests**

Run: `conda run -n news-caught pytest backend/tests/test_llm_config.py -q`
Expected: PASS.

## Chunk 2: Frontend Settings Page

### Task 3: Add failing frontend tests for settings page states

**Files:**
- Create: `frontend/src/views/LlmSettingsView.test.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Write the failing empty-state test**

Assert the page shows an empty form and explanatory text when config is not set.

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts`
Expected: FAIL because the route/view/store do not exist yet.

- [ ] **Step 3: Write the failing populated-state/save test**

Assert the page:
- fills provider/model/base_url/display_name from existing config
- allows entering a new key or leaving it blank
- calls save and shows success state

- [ ] **Step 4: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts`
Expected: FAIL because the save wiring does not exist yet.

### Task 4: Implement LLM settings route, store, and page

**Files:**
- Create: `frontend/src/stores/llmStore.ts`
- Create: `frontend/src/views/LlmSettingsView.vue`
- Create: `frontend/src/views/LlmSettingsView.test.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/AppShell.vue`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/views/NewsDetailView.vue`
- Modify: `frontend/src/views/NewsDetailView.test.ts`
- Optionally modify: `frontend/src/stores/newsStore.ts`

- [ ] **Step 1: Add dedicated LLM settings store**
- [ ] **Step 2: Add `saveLlmConfig` client method**
- [ ] **Step 3: Build the settings page form and inline success/error states**
- [ ] **Step 4: Add navigation and route wiring**
- [ ] **Step 5: Rewire news detail page to read config from the dedicated LLM store**
- [ ] **Step 6: Run focused frontend tests**

Run: `npm --prefix frontend run test -- --run src/views/LlmSettingsView.test.ts src/views/NewsDetailView.test.ts`
Expected: PASS.

## Chunk 3: Verification And Records

### Task 5: Full verification and change log update

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS.

- [ ] **Step 2: Run frontend verification**

Run: `npm --prefix frontend run test -- --run`
Expected: PASS.

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 3: Update change log**

Add one top entry summarizing:
- the new settings page
- the backend preserve-key behavior
- verification evidence
- remaining risks around plaintext key storage
