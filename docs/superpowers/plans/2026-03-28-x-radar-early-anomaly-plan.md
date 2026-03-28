# X Radar Early Anomaly Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild X Monitor into an X Radar page that produces sortable early anomaly signals from a custom account pool plus macro or policy event rules.

**Architecture:** Keep raw post ingestion in place, add a separate signal layer on top of `x_post`, expose a new radar query API for the page, and refactor provider access behind a stable protocol so provider churn does not leak into the rest of the module.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic, Vue 3, Pinia, Vitest, Pytest

---

## Chunk 1: Signal Data Model And Provider Boundary

### Task 1: Add failing backend tests for provider abstraction and radar models

**Files:**
- Modify: `backend/tests/test_x_monitor.py`
- Create: `backend/app/models/x_signal.py`
- Create: `backend/app/models/x_signal_post_link.py`
- Modify: `backend/app/services/twitterapi_io_client.py`
- Modify: `backend/app/services/x_monitor.py`

- [ ] **Step 1: Write failing tests for radar data model expectations**

Add tests in `backend/tests/test_x_monitor.py` that expect:

- refresh can persist generated radar signals
- signal rows can link to one or more evidence posts
- provider errors remain isolated to provider health behavior

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'signal or radar or provider' -q`
Expected: FAIL because `x_signal` models and radar logic do not exist yet

- [ ] **Step 3: Add the new models and provider protocol**

Implement:

- `backend/app/models/x_signal.py`
- `backend/app/models/x_signal_post_link.py`

Add a provider-facing protocol or base interface in the X services area and adapt `twitterapi.io` access behind it.

- [ ] **Step 4: Run the focused tests to verify the new structures load**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'signal or radar or provider' -q`
Expected: tests advance past import or model errors and fail only on missing behavior

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_x_monitor.py backend/app/models/x_signal.py backend/app/models/x_signal_post_link.py backend/app/services/twitterapi_io_client.py backend/app/services/x_monitor.py
git commit -m "feat: add x radar signal models"
```

### Task 2: Wire models into the ORM and schema layer

**Files:**
- Modify: `backend/app/models/__init__` or the project model registry files that load ORM models
- Modify: `backend/app/schemas/x_monitor.py`
- Modify: `backend/tests/test_x_monitor.py`

- [ ] **Step 1: Write failing schema tests for radar responses**

Add tests that expect radar response objects with:

- `priority_signals`
- `macro_clusters`
- `evidence_stream`

- [ ] **Step 2: Run the schema-focused tests to verify failure**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'radar response or macro cluster' -q`
Expected: FAIL because schemas are missing

- [ ] **Step 3: Add minimal response schemas**

Implement minimal Pydantic models for:

- signal cards
- macro clusters
- radar response wrapper

- [ ] **Step 4: Run the schema-focused tests to verify pass**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'radar response or macro cluster' -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/x_monitor.py backend/tests/test_x_monitor.py
git commit -m "feat: add x radar response schemas"
```

## Chunk 2: Signal Builder And Radar API

### Task 3: Add failing backend tests for signal generation

**Files:**
- Modify: `backend/tests/test_x_monitor.py`
- Create: `backend/app/services/x_radar_signal_builder.py`
- Modify: `backend/app/services/x_monitor.py`

- [ ] **Step 1: Write failing tests for signal generation rules**

Cover:

- core account post becomes a priority signal
- macro keywords generate a `macro_event` signal
- two accounts hitting the same macro tag within the window create a `multi_account_resonance` signal

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'macro_event or resonance or priority signal' -q`
Expected: FAIL because signal builder does not exist

- [ ] **Step 3: Implement the minimal signal builder**

Add `backend/app/services/x_radar_signal_builder.py` with:

- macro keyword configuration
- account weight rules
- novelty and resonance calculation helpers
- signal creation and evidence linking

Keep the first version rule-based and deterministic.

- [ ] **Step 4: Integrate the builder into refresh flow**

Update `backend/app/services/x_monitor.py` so refresh:

- ingests raw posts
- triggers signal build or rebuild for the newly inserted posts

- [ ] **Step 5: Run the focused tests to verify pass**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'macro_event or resonance or priority signal' -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_x_monitor.py backend/app/services/x_radar_signal_builder.py backend/app/services/x_monitor.py
git commit -m "feat: build x radar signals from posts"
```

### Task 4: Add the radar query API

**Files:**
- Modify: `backend/app/api/routes/x_monitor.py`
- Modify: `backend/app/services/x_monitor.py`
- Add or modify any repository helpers needed for radar queries
- Modify: `backend/tests/test_x_monitor.py`

- [ ] **Step 1: Write failing API tests for `GET /api/x/radar`**

Test:

- endpoint returns grouped signal cards
- evidence feed remains available
- radar output is ordered by priority

- [ ] **Step 2: Run the endpoint tests to verify failure**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'api/x/radar or radar endpoint' -q`
Expected: FAIL because route is missing

- [ ] **Step 3: Implement minimal query and route logic**

Add:

- repository or query helpers for signal cards
- `GET /api/x/radar`
- response mapping

- [ ] **Step 4: Run the endpoint tests to verify pass**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'api/x/radar or radar endpoint' -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/x_monitor.py backend/app/services/x_monitor.py backend/tests/test_x_monitor.py
git commit -m "feat: expose x radar api"
```

## Chunk 3: Frontend Radar Experience

### Task 5: Add failing frontend tests for radar page structure

**Files:**
- Modify: `frontend/src/views/XMonitorView.test.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/stores/xMonitorStore.ts`

- [ ] **Step 1: Write failing view tests for the new radar layout**

Expect:

- page title becomes `X Radar`
- page renders `Priority Radar`, `Macro Watch`, and `Evidence Feed`
- top cards render signal titles and evidence counts

- [ ] **Step 2: Run the focused frontend tests to verify failure**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: FAIL because radar types and layout do not exist

- [ ] **Step 3: Add API and store support for radar data**

Implement:

- new TypeScript API types
- `getXRadar()` client method
- store state for radar payload

- [ ] **Step 4: Run the focused frontend tests to advance failures**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: tests now fail only on missing final layout or content details

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/XMonitorView.test.ts frontend/src/types/api.ts frontend/src/api/client.ts frontend/src/api/mock.ts frontend/src/stores/xMonitorStore.ts
git commit -m "feat: add x radar frontend data layer"
```

### Task 6: Implement the radar page UI without breaking account operations

**Files:**
- Modify: `frontend/src/views/XMonitorView.vue`
- Add helper components only if the view becomes too large
- Modify: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 1: Implement the minimal radar-first layout**

Render:

- top status banner
- `Priority Radar`
- `Macro Watch`
- `Evidence Feed`
- account management area in a secondary position

- [ ] **Step 2: Keep evidence and account management behaviors working**

Ensure:

- refresh still works
- account create, toggle, delete, import, export still work
- evidence feed still supports translation and raw post viewing

- [ ] **Step 3: Run the focused frontend tests to verify pass**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/XMonitorView.vue frontend/src/views/XMonitorView.test.ts
git commit -m "feat: redesign x monitor as x radar"
```

## Chunk 4: Verification, Docs, And Recordkeeping

### Task 7: Run full relevant verification

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend view verification**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: PASS

- [ ] **Step 3: Run frontend build verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Update the change log**

Append a top entry to `docs/code-change-log.md` covering:

- x radar repositioning
- signal layer addition
- new API shape
- verification results

- [ ] **Step 5: Commit**

```bash
git add docs/code-change-log.md
git commit -m "docs: record x radar early anomaly rollout"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-28-x-radar-early-anomaly-plan.md`. Ready to execute?
