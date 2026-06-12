# LLM Connection Test Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 LLM 设置页新增“保存后测试连接”能力，并透传上游 LLM 的真实鉴权错误信息。

**Architecture:** 后端新增基于当前激活配置的 `POST /api/llm/test` 接口，前端通过 store 调用该接口并显示独立状态。provider 错误处理增强为优先返回上游错误正文，避免只看到裸状态码。

**Tech Stack:** FastAPI, SQLAlchemy, httpx, Vue 3, Pinia, Vitest, pytest

---

## File Map

- Modify: `backend/app/services/llm_providers.py`
- Modify: `backend/app/api/routes/llm.py`
- Modify: `backend/app/schemas/llm.py`
- Modify: `backend/tests/test_news_analysis.py`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/client.test.ts`
- Modify: `frontend/src/stores/llmStore.ts`
- Modify: `frontend/src/views/LlmSettingsView.vue`
- Modify: `frontend/src/views/LlmSettingsView.test.ts`
- Modify: `docs/code-change-log.md`

## Chunk 1: Backend Test Endpoint and Error Detail

### Task 1: Write failing backend tests

**Files:**
- Modify: `backend/tests/test_news_analysis.py`

- [ ] **Step 1: Write failing tests**
  - `POST /api/llm/test` returns `400` when no config exists
  - `POST /api/llm/test` returns success payload when provider call succeeds
  - provider 401 response surfaces upstream message instead of bare status code

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_analysis.py -q -k 'llm_test or authentication_error'`
Expected: FAIL because endpoint and error detail behavior do not exist yet.

- [ ] **Step 3: Write minimal implementation**
  - Add response schema
  - Add route
  - Add provider helper for connection test
  - Parse upstream error bodies for message detail

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_analysis.py -q -k 'llm_test or authentication_error'`
Expected: PASS

## Chunk 2: Frontend Button and State

### Task 2: Write failing frontend tests

**Files:**
- Modify: `frontend/src/api/client.test.ts`
- Modify: `frontend/src/views/LlmSettingsView.test.ts`
- Modify: `frontend/src/stores/llmStore.ts`

- [ ] **Step 1: Write failing tests**
  - API client posts `/api/llm/test`
  - Settings view renders a test button when config exists
  - Clicking test button calls store action and shows success/failure

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/views/LlmSettingsView.test.ts`
Expected: FAIL because no client/store/view test-connection behavior exists.

- [ ] **Step 3: Write minimal implementation**
  - Add response type and client method
  - Add store state/action for test connection
  - Add button and status area to view

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/views/LlmSettingsView.test.ts`
Expected: PASS

## Chunk 3: Final Verification and Logging

### Task 3: Run project verification and update log

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_news_analysis.py backend/tests/test_llm_config.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/views/LlmSettingsView.test.ts`
Expected: PASS

- [ ] **Step 3: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Update change log**

记录新接口、页面交互、验证结果和已确认的真实 401 根因。
