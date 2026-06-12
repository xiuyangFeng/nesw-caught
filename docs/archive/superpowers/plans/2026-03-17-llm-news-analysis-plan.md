# LLM News Analysis Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manually triggered, multi-provider LLM analysis flow on the news detail page that identifies candidate stocks, highlights one top pick, and persists both provider config and analysis results.

**Architecture:** Add a dedicated backend LLM configuration and news analysis module that is isolated from the existing X Monitor chain. Persist one active provider config plus per-news analysis results, expose config and analysis APIs, and extend the news detail view to read cached analysis results and trigger fresh analysis on demand.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, httpx, Vue 3, Pinia, pytest, Vitest-ready frontend build

---

## Chunk 1: Backend Models And Configuration API

### Task 1: Add failing backend tests for provider configuration persistence and API behavior

**Files:**
- Create: `backend/tests/test_llm_config.py`

- [ ] **Step 1: Write the failing config persistence test**

Add a test covering:
- saving a provider config with `provider_name`, `base_url`, `model_name`, and `api_key`
- reading back the active config without exposing the raw key in the response model

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_llm_config.py -q`
Expected: FAIL because the model/repository/route does not exist yet.

- [ ] **Step 3: Write the failing config API test**

Add API tests for:
- `GET /api/llm/config` when nothing is configured
- `POST /api/llm/config` creating or updating the active config

- [ ] **Step 4: Run the focused test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_llm_config.py -q`
Expected: FAIL because the route and schemas do not exist yet.

### Task 2: Implement provider config model, repository, schemas, and routes

**Files:**
- Create: `backend/app/models/llm_provider_config.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/db/initializer.py`
- Create: `backend/app/repositories/llm_provider_config_repository.py`
- Create: `backend/app/schemas/llm.py`
- Create: `backend/app/api/routes/llm.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: Add the SQLAlchemy model**

Implement fields for:
- provider name
- display name
- base URL
- model name
- API key storage
- active flag
- created/updated timestamps

- [ ] **Step 2: Add repository methods**

Implement:
- get active config
- upsert active config
- deactivate previous configs if needed

- [ ] **Step 3: Add Pydantic schemas**

Provide:
- request schema for saving config
- response schema that masks or omits raw API key
- empty-state response shape for “not configured”

- [ ] **Step 4: Add config routes**

Implement:
- `GET /api/llm/config`
- `POST /api/llm/config`

- [ ] **Step 5: Run focused backend tests**

Run: `conda run -n news-caught pytest backend/tests/test_llm_config.py -q`
Expected: PASS.

## Chunk 2: Backend News Analysis Flow

### Task 3: Add failing backend tests for analysis result storage and manual analysis API

**Files:**
- Create: `backend/tests/test_news_analysis.py`

- [ ] **Step 1: Write the failing success-path analysis test**

Add a test for `POST /api/news/{news_id}/analyze` that:
- seeds a news row with article content
- seeds an active provider config
- stubs the provider client response with valid JSON
- asserts the response includes `top_pick`, `candidates`, `summary`, `risk_notes`, and provider/model metadata

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_analysis.py -q`
Expected: FAIL because the model/service/route does not exist yet.

- [ ] **Step 3: Write failing error-path tests**

Cover:
- news not found
- provider not configured
- article body missing and fallback to title/summary
- provider returns invalid JSON

- [ ] **Step 4: Run the focused test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_analysis.py -q`
Expected: FAIL with missing route or missing service behavior.

### Task 4: Implement analysis result model, provider abstraction, and analysis endpoints

**Files:**
- Create: `backend/app/models/news_analysis_result.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/db/initializer.py`
- Create: `backend/app/repositories/news_analysis_repository.py`
- Create: `backend/app/services/llm_providers.py`
- Create: `backend/app/services/news_analysis.py`
- Modify: `backend/app/repositories/news_repository.py`
- Modify: `backend/app/schemas/llm.py`
- Modify: `backend/app/api/routes/news.py`

- [ ] **Step 1: Add the analysis result model and repository**

Persist:
- `news_id`
- `provider_name`
- `model_name`
- `analysis_status`
- `top_pick_*`
- `summary`
- `risk_notes`
- `sentiment`
- `raw_response_json`
- `analysis_error`
- `analyzed_at`

- [ ] **Step 2: Add a provider abstraction**

Implement a minimal interface that accepts:
- active provider config
- normalized prompt payload

Return parsed JSON or raise typed provider errors.

First implementation target:
- one openai-compatible client with configurable `base_url`

Keep the interface extensible for future provider-specific implementations.

- [ ] **Step 3: Implement the news analysis service**

Service responsibilities:
- load the news item and article content
- build the prompt from title, summary, body, source, market, timestamp
- mark context limitations when full article text is unavailable
- call the provider
- validate and normalize the JSON payload
- persist the latest analysis result

- [ ] **Step 4: Add analysis schemas and routes**

Implement:
- `GET /api/news/{news_id}/analysis`
- `POST /api/news/{news_id}/analyze`

Response should expose:
- top pick
- candidates
- summary
- risk notes
- sentiment
- provider name
- model name
- analyzed timestamp
- context limitations if present

- [ ] **Step 5: Run focused backend tests**

Run: `conda run -n news-caught pytest backend/tests/test_news_analysis.py -q`
Expected: PASS.

## Chunk 3: Frontend Detail View And API Integration

### Task 5: Add failing frontend tests or view-state checks for manual LLM analysis

**Files:**
- Modify: `frontend/src/views/NewsDetailView.test.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add the failing “not configured” view test**

Assert that when the analysis API indicates no provider config, the page shows a clear empty state instead of a generic error.

- [ ] **Step 2: Run the focused frontend test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts`
Expected: FAIL because the analysis state and UI do not exist yet.

- [ ] **Step 3: Add the failing “successful analysis render” test**

Assert that the page renders:
- top pick card
- candidate list
- recommendation reason

- [ ] **Step 4: Run the focused frontend test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts`
Expected: FAIL because the analysis API/store wiring is missing.

### Task 6: Implement frontend analysis types, API client methods, store state, and detail view UI

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/stores/newsStore.ts`
- Modify: `frontend/src/views/NewsDetailView.vue`
- Optionally create: `frontend/src/components/news/NewsAnalysisPanel.vue`

- [ ] **Step 1: Add API types**

Define:
- provider config summary type
- news analysis result type
- top pick and candidate item types

- [ ] **Step 2: Add client methods**

Implement:
- `getLlmConfig`
- `getNewsAnalysis`
- `analyzeNews`

- [ ] **Step 3: Extend the news store**

Track:
- per-news analysis result map
- analysis loading state
- analysis error state
- config availability state if the view needs it centrally

- [ ] **Step 4: Update the news detail page**

Add:
- analysis section
- manual trigger button
- loading/error/empty/success states
- top pick presentation
- candidate list and reasons
- provider/model/analyzed-at metadata

- [ ] **Step 5: Run focused frontend tests**

Run: `npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts`
Expected: PASS.

## Chunk 4: Verification And Records

### Task 7: Full verification and change log update

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run targeted backend tests**

Run: `conda run -n news-caught pytest backend/tests/test_llm_config.py backend/tests/test_news_analysis.py -q`
Expected: PASS.

- [ ] **Step 2: Run full backend verification**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS.

- [ ] **Step 3: Run focused frontend tests**

Run: `npm --prefix frontend run test -- --run src/views/NewsDetailView.test.ts`
Expected: PASS.

- [ ] **Step 4: Run full frontend verification**

Run: `npm --prefix frontend run test -- --run`
Expected: PASS.

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 5: Update the change log**

Add one top entry summarizing:
- new config model/API
- new news analysis model/API
- frontend manual analysis interaction
- verification evidence
- residual risks, especially around API key storage and model reliability
