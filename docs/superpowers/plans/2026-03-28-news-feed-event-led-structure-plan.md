# News Feed Event-Led Structure Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an event-led mixed news feed where the homepage shows derived event cards first, topic watch second, and the raw news stream third.

**Architecture:** Add a backend feed-layout service that derives event cards from existing `topic_cluster`, `news_item`, and `news_stock_mention` data without introducing a new persistent event table. Expose the layout through a dedicated API route, then wire the frontend store and `NewsFeedView` to render the event-first layout while preserving the existing raw stream as fallback.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Pinia, Vitest, pytest

---

## Chunk 1: Backend Feed Layout Contract

### Task 1: Add failing backend tests for derived event feed layout

**Files:**
- Modify: `backend/tests/test_news.py`
- Modify: `backend/tests/test_news_signal_pipeline.py` (reference patterns only if needed)
- Test: `backend/tests/test_news.py`

- [ ] **Step 1: Write the failing API contract test**

Add a test that seeds recent news, mentions, and topics, then calls `GET /api/news/feed-layout` and asserts:
- `events` is present and sorted by importance / freshness
- each event exposes `event_key`, `event_title`, `event_type`, `related_symbols`, `news_items`
- `topics` and `stream` are both present

- [ ] **Step 2: Run the backend test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news.py -k feed_layout -v`
Expected: FAIL because the route/schema/service do not exist yet

- [ ] **Step 3: Add minimal schemas and route support**

Implement:
- Pydantic response models in `backend/app/schemas/news.py`
- a new route handler in `backend/app/api/routes/news.py`
- a small service module to build the layout from existing repositories

- [ ] **Step 4: Run the backend test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_news.py -k feed_layout -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_news.py backend/app/schemas/news.py backend/app/api/routes/news.py backend/app/services/news_feed_layout.py
git commit -m "feat: add event-led news feed layout api"
```

## Chunk 2: Backend Event Derivation Rules

### Task 2: Add failing unit tests for event derivation and classification

**Files:**
- Create: `backend/tests/test_news_feed_layout.py`
- Create: `backend/app/services/news_feed_layout.py`
- Test: `backend/tests/test_news_feed_layout.py`

- [ ] **Step 1: Write the failing service tests**

Add tests that verify:
- only qualifying topics become events
- `event_type` is inferred from titles / summaries / keywords
- `primary_symbol` and `related_symbols` are frequency-ranked
- event cards include only the top few news items

- [ ] **Step 2: Run the unit tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -v`
Expected: FAIL because the service and helper functions are missing

- [ ] **Step 3: Implement the minimal derivation logic**

Implement:
- event candidate qualification
- heuristic event type classification
- symbol aggregation
- event sorting
- topic watch and raw stream slicing

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_news_feed_layout.py backend/app/services/news_feed_layout.py
git commit -m "feat: derive event cards for news feed"
```

## Chunk 3: Frontend Event Feed Consumption

### Task 3: Add failing frontend tests for event-led rendering

**Files:**
- Modify: `frontend/src/views/NewsFeedView.test.ts`
- Modify: `frontend/src/stores/newsStore.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/components/news/EventFeedCard.vue`
- Test: `frontend/src/views/NewsFeedView.test.ts`

- [ ] **Step 1: Write the failing frontend tests**

Add tests that verify:
- `NewsFeedView` renders an `Event Radar` section before `News Stream`
- event cards show type, symbols, and mounted story headlines
- when no events are returned, the raw stream still renders

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts`
Expected: FAIL because the store/client/types/view do not support the new layout

- [ ] **Step 3: Implement minimal frontend support**

Implement:
- API client method and types for `feed-layout`
- store state/load function for feed layout
- event card component
- `NewsFeedView` section ordering: `Event Radar` -> `Topic Watch` -> `News Stream`

- [ ] **Step 4: Run the frontend tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/NewsFeedView.test.ts frontend/src/stores/newsStore.ts frontend/src/types/api.ts frontend/src/api/client.ts frontend/src/components/news/EventFeedCard.vue frontend/src/views/NewsFeedView.vue
git commit -m "feat: render event-led news feed"
```

## Chunk 4: Verification And Project Record

### Task 4: Update records and verify the end-to-end slice

**Files:**
- Modify: `docs/code-change-log.md`
- Modify: `docs/superpowers/specs/2026-03-28-news-feed-event-led-structure-design.md` (only if implementation diverges)
- Modify: `docs/superpowers/plans/2026-03-28-news-feed-event-led-structure-plan.md` (checklist updates if needed)

- [ ] **Step 1: Update the change log entry**

Append a new top entry to `docs/code-change-log.md` covering:
- event-led homepage layout
- new backend feed-layout API
- tests run and outcomes
- any deferred risks

- [ ] **Step 2: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py backend/tests/test_news_signal_pipeline.py`
Expected: PASS

- [ ] **Step 3: Run frontend verification**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts`
Expected: PASS

- [ ] **Step 4: Run frontend build verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/code-change-log.md docs/superpowers/specs/2026-03-28-news-feed-event-led-structure-design.md docs/superpowers/plans/2026-03-28-news-feed-event-led-structure-plan.md
git commit -m "docs: record event-led news feed work"
```

Plan complete and saved to `docs/superpowers/plans/2026-03-28-news-feed-event-led-structure-plan.md`. Execution proceeds in this session.
