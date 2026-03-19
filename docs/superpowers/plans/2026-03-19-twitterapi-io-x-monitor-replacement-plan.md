# TwitterAPI.io X Monitor Replacement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing `grok-bridge` powered `X Monitor` module with a direct `twitterapi.io` provider, keep account-monitoring persistence, add manual keyword search, and remove the bridge-specific configuration and UX.

**Architecture:** Keep the current `/api/x/*` and `X Monitor` product surface, but swap the provider implementation behind `XMonitorService`. Add a focused `twitterapi.io` client for authenticated HTTP access, keep account refresh writing into existing `x_*` tables, add a new `/api/x/search` read-only search endpoint, and normalize health responses away from `bridge_*` fields.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic Settings, pytest, Vue 3, Pinia, TypeScript, Vitest, Vite

---

## Chunk 1: Replace The Provider Contract In Backend Tests

### Task 1: Lock the new provider configuration and health shape with failing backend tests

**Files:**
- Modify: `backend/tests/test_x_monitor.py`
- Test: `backend/tests/test_x_monitor.py`

- [ ] **Step 1: Replace bridge client tests with twitterapi.io client expectations**

Add or rewrite tests so they assert:
- the new client sends `X-API-Key`
- the new client uses `TWITTERAPI_IO_TIMEOUT_SECONDS`
- JSON decoding failures and non-2xx responses raise provider-specific errors

- [ ] **Step 2: Add a failing refresh test for direct tweet ingestion**

Update the refresh test to use a fake `TwitterApiIoClient` that returns tweet-shaped data and assert:
- refresh reads the local accounts file
- fetched tweets are mapped into `x_post`
- duplicate tweet ids are ignored on the second refresh

- [ ] **Step 3: Add a failing search endpoint test**

Add a new API test for `GET /api/x/search` that asserts:
- `q` is required
- response rows are normalized into the same summary shape used by the UI

- [ ] **Step 4: Add a failing health endpoint test for provider semantics**

Update the health test to assert:
- `/api/health` exposes `x_monitor_enabled` and `x_monitor_healthy`
- `/api/health/x` exposes `configured`, `healthy`, and `status`
- provider name is `twitterapi.io`

- [ ] **Step 5: Run the backend test file to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -q`
Expected: FAIL because the implementation still imports `GrokBridgeClient`, still returns `bridge_*` fields, and does not expose `/api/x/search`.

## Chunk 2: Implement The TwitterAPI.io Backend Provider

### Task 2: Add the twitterapi.io client and remove bridge-only configuration

**Files:**
- Create: `backend/app/services/twitterapi_io_client.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/x_monitor.py`
- Modify: `backend/app/api/routes/health.py`
- Modify: `backend/app/schemas/x_monitor.py`
- Modify: `backend/app/schemas/health.py`
- Delete: `backend/app/services/grok_bridge_client.py`
- Test: `backend/tests/test_x_monitor.py`

- [ ] **Step 1: Add the new settings fields**

In `backend/app/core/config.py`, remove:
- `grok_bridge_base_url`
- `grok_bridge_timeout_seconds`

Add:
- `twitterapi_io_api_key: str | None = None`
- `twitterapi_io_timeout_seconds: float = 60.0`

- [ ] **Step 2: Implement a minimal provider client**

In `backend/app/services/twitterapi_io_client.py`, add:
- a `TwitterApiIoError` exception
- a client class that reads settings via `get_settings()`
- request helpers for:
  - `get_user_last_tweets(handle: str, limit: int = 20)`
  - `advanced_search(query: str, limit: int = 20)`
- response validation that fails loudly on missing payload structure

- [ ] **Step 3: Swap `XMonitorService` to the new client**

In `backend/app/services/x_monitor.py`:
- replace `GrokBridgeClient` usage with `TwitterApiIoClient`
- remove prompt building and JSON array extraction logic
- add tweet-to-domain mapping helpers
- keep local account sync
- keep persistence into existing repositories
- change dedupe priority to:
  - first `external_post_id`
  - then `canonical_url`
  - then content hash fallback only if needed

- [ ] **Step 4: Add backend keyword search support**

Extend `XMonitorService` with a `search_posts(query: str, limit: int)` path that:
- calls `advanced_search`
- maps tweets into `XPostSummaryView`-compatible rows
- does not write search results to the database

- [ ] **Step 5: Update health schemas and handlers**

In `backend/app/schemas/x_monitor.py` and `backend/app/api/routes/health.py`:
- rename `bridge_configured` -> `configured`
- rename `bridge_healthy` -> `healthy`
- rename `bridge_status` -> `status`
- update global health fields from `x_bridge_*` to `x_monitor_*`
- determine `healthy` from enabled/configured state plus a provider-health check

- [ ] **Step 6: Add the new search route**

In `backend/app/api/routes/x_monitor.py`:
- add `GET /api/x/search`
- validate `q`
- return normalized search rows

- [ ] **Step 7: Run focused backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -q`
Expected: PASS

### Task 3: Verify the provider replacement against surrounding backend behavior

**Files:**
- Modify: `backend/app/api/routes/x_monitor.py`
- Modify: `backend/app/api/routes/health.py`
- Modify: `backend/app/api/router.py` only if route wiring changes are needed
- Test: `backend/tests/test_x_monitor.py`

- [ ] **Step 1: Run related backend tests**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS, including the updated X monitor tests and no regressions from health schema changes.

- [ ] **Step 2: Adjust any health or router compatibility gaps**

If failures show dependent code still expecting `bridge_*` fields or old imports, patch only the necessary schema and route call sites.

- [ ] **Step 3: Re-run the full backend suite**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS

## Chunk 3: Update Frontend Types, Store, And View

### Task 4: Lock the new frontend X monitor behavior with failing tests

**Files:**
- Modify: `frontend/src/views/XMonitorView.vue`
- Modify: `frontend/src/stores/xMonitorStore.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/mock.ts`
- Create or Modify: `frontend/src/views/XMonitorView.test.ts`
- Test: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 1: Add a failing X Monitor view test for provider wording and keyword search**

Add assertions that the page:
- shows `twitterapi.io` wording instead of `grok-bridge`
- reads `health.configured`, `health.healthy`, and `health.status`
- exposes a keyword search input and search trigger
- renders search results independently from persisted account posts

- [ ] **Step 2: Run the targeted frontend test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: FAIL because the current page only supports bridge health and account posts.

### Task 5: Implement the frontend provider and search UI

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/stores/xMonitorStore.ts`
- Modify: `frontend/src/views/XMonitorView.vue`
- Test: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 1: Update API and domain types**

In `frontend/src/types/api.ts`:
- rename `XHealth` fields to `configured`, `healthy`, `status`
- update `HealthStatus` fields to `x_monitor_enabled` and `x_monitor_healthy`
- add a search result type if the response shape diverges from `XPost`

- [ ] **Step 2: Extend the API client and mocks**

In `frontend/src/api/client.ts` and `frontend/src/api/mock.ts`:
- update health fallback data to provider wording
- add `getXSearchResults({ q, limit })`
- add mock search rows for the page test

- [ ] **Step 3: Extend the Pinia store**

In `frontend/src/stores/xMonitorStore.ts`, add:
- search query state
- search loading state
- search results state
- a `searchPosts()` action
- bootstrap behavior that does not auto-run search

- [ ] **Step 4: Update the view**

In `frontend/src/views/XMonitorView.vue`:
- replace all `grok-bridge` wording with `twitterapi.io`
- update banner and metrics to the new health shape
- add a keyword search panel and result list
- keep the account-monitoring area as the persisted feed

- [ ] **Step 5: Run the targeted X Monitor frontend test**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: PASS

## Chunk 4: Documentation, Cleanup, And Verification

### Task 6: Remove bridge-specific docs and local setup guidance

**Files:**
- Modify: `README.md`
- Modify: `.env` only if the repository intentionally tracks an example entry here
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Replace the README setup section**

Update the `X Monitor` section so it documents:
- `TWITTERAPI_IO_API_KEY`
- `TWITTERAPI_IO_TIMEOUT_SECONDS`
- `X_MONITOR_ACCOUNTS_FILE`
- `/api/x/search` in addition to the existing routes

- [ ] **Step 2: Remove bridge startup instructions**

Delete references to:
- local `grok-bridge` repositories
- standalone bridge process startup
- Safari or `grok.com` prerequisites

- [ ] **Step 3: Update the code change log**

Add a top entry to `docs/code-change-log.md` covering:
- bridge removal
- twitterapi.io provider integration
- backend and frontend files changed
- tests run
- residual risk around real API response mapping and API-key-backed verification

### Task 7: Run final project verification

**Files:**
- Modify: `docs/code-change-log.md` only if verification notes need correction

- [ ] **Step 1: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 3: Perform manual API-backed smoke testing when credentials are available**

Required user inputs before this step:
- a valid `TWITTERAPI_IO_API_KEY`
- the account list file the user wants monitored

Smoke checks:
- `GET /api/health/x` shows configured provider state
- `POST /api/x/refresh` ingests recent tweets from the supplied accounts
- `GET /api/x/posts` returns persisted rows
- `GET /api/x/search?q=...` returns live search results

- [ ] **Step 4: Record any credential-blocked verification explicitly**

If the user has not yet provided a real API key and account list, leave the automated verification complete but mark live provider smoke testing as pending user-supplied credentials.
