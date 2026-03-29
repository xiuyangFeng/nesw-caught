# Event Detail API Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove EventDetailView's dependence on the frontend feed-layout snapshot by adding a reconstructable backend event-detail API and switching the view to request it directly.

**Architecture:** Reuse the existing feed-layout aggregation pipeline on the backend to reconstruct current event cards and expose `GET /api/news/events/{event_key}`. Frontend event detail becomes an API-driven page with explicit loading, not-found, and error states instead of reading from `newsStore.feedLayout.events`.

**Tech Stack:** FastAPI, SQLAlchemy repositories, Pydantic schemas, Vue 3, Vitest, existing frontend API client

---

## Chunk 1: Backend event-detail API

### Task 1: Add failing backend tests for event-detail API

**Files:**
- Modify: `backend/tests/test_news.py`
- Modify: `backend/tests/test_news_feed_layout.py`
- Modify: `backend/app/api/routes/news.py`
- Modify: `backend/app/schemas/news.py`

- [ ] **Step 1: Write the failing test for topic event detail lookup**

Add a backend API test asserting `GET /api/news/events/topic-<id>` returns 200 with the full `NewsEventDetailView` shape and complete mounted news timeline.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news.py -q`
Expected: FAIL because the route does not exist yet.

- [ ] **Step 3: Write the failing test for fused event detail lookup**

Add a service-level or API-level test asserting a `fused-*` event key can be reconstructed by exact key match and returned with complete `news_items`.

- [ ] **Step 4: Run the focused fused-event test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -q`
Expected: FAIL because no event-detail lookup method exists yet.

- [ ] **Step 5: Write the failing 404 test**

Add a test asserting an unknown `event_key` returns 404 with a stable error detail.

- [ ] **Step 6: Run the focused backend tests to confirm red**

Run: `conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py -q`
Expected: FAIL for the missing route/service behavior.

- [ ] **Step 7: Implement the minimal backend event-detail API**

Update schemas, `NewsFeedLayoutService`, and `/api/news` routes just enough to satisfy the new event-detail behavior, including:
- a precise `NewsEventDetailView` response model
- full `news_items` in detail responses
- `/events/{event_key}` route registration before `/{news_id}`
- stable detail-side sorting contract: `published_at`, then `fetched_at`, then `id`

- [ ] **Step 8: Re-run the focused backend tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py -q`
Expected: PASS.

## Chunk 2: Frontend EventDetailView switches to API

### Task 2: Add failing frontend tests for direct event-detail API loading

**Files:**
- Create: `frontend/src/views/EventDetailView.vue`
- Create: `frontend/src/views/EventDetailView.test.ts`
- Modify: `frontend/src/api/client.test.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/router/index.test.ts`

- [ ] **Step 1: Write the failing API client test**

Add a test asserting `apiClient.getNewsEventDetail('topic-1')` requests `/api/news/events/topic-1`.

- [ ] **Step 2: Run the focused API client test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts`
Expected: FAIL because the client method is missing.

- [ ] **Step 3: Write the failing EventDetailView success-path test**

Update the view test to assert it calls `getNewsEventDetail(eventKey)` and renders the returned event summary plus sorted timeline.

- [ ] **Step 4: Write the failing not-found and generic-error tests**

Add separate tests for a 404 response and a non-404 error response.

- [ ] **Step 5: Run the focused EventDetailView tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/views/EventDetailView.test.ts`
Expected: FAIL because the view still reads from `newsStore.feedLayout.events`.

- [ ] **Step 6: Implement the minimal frontend API integration**

Add the new API client/type support, create `EventDetailView.vue`, and wire `frontend/src/router/index.ts` so the new page is actually reachable with explicit loading/error states.

- [ ] **Step 7: Re-run the focused frontend tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/views/EventDetailView.test.ts src/router/index.test.ts`
Expected: PASS.

## Chunk 3: Records and full verification

### Task 3: Update project records and run verification

**Files:**
- Modify: `docs/code-change-log.md`
- Modify: `docs/superpowers/specs/2026-03-30-event-detail-api-design.md`
- Modify: `docs/superpowers/plans/2026-03-30-event-detail-api-plan.md`

- [ ] **Step 1: Update the code change log**

Add a new top entry describing the backend event-detail API, frontend view migration, and validation commands.

- [ ] **Step 2: Run targeted backend and frontend tests**

Run: `conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py -q && npm --prefix frontend run test -- --run src/api/client.test.ts src/views/EventDetailView.test.ts src/router/index.test.ts`
Expected: PASS.

- [ ] **Step 3: Run the frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS.

- [ ] **Step 4: Run the full frontend test suite**

Run: `npm --prefix frontend run test -- --run`
Expected: PASS.

- [ ] **Step 5: Review diff and commit**

Run:
```bash
git status --short
git add backend/app/api/routes/news.py backend/app/schemas/news.py backend/app/services/news_feed_layout.py backend/tests/test_news.py backend/tests/test_news_feed_layout.py frontend/src/api/client.ts frontend/src/api/client.test.ts frontend/src/types/api.ts frontend/src/views/EventDetailView.vue frontend/src/views/EventDetailView.test.ts frontend/src/router/index.ts frontend/src/router/index.test.ts docs/superpowers/specs/2026-03-30-event-detail-api-design.md docs/superpowers/plans/2026-03-30-event-detail-api-plan.md docs/code-change-log.md
git commit -m "feat: add reconstructable event detail api"
```
