# News Portfolio Hit Strip Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compact watchlist-hit strip to news event cards without making the cards materially taller.

**Architecture:** Extend the backend event contract with `watchlist_hits`, compute it inside the existing news feed layout service from stored watchlist items in stable event-symbol order, then render a single-line compact hit strip in event cards. Keep all explanation logic and event-detail changes out of scope.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Pinia, Vitest, pytest

---

## Chunk 1: Backend Contract And Ranking

### Task 1: Add failing backend tests for watchlist hits

**Files:**
- Modify: `backend/tests/test_news_feed_layout.py`
- Modify: `backend/tests/test_news.py`

- [ ] **Step 1: Write the failing tests**

Add assertions that:
- `build_event_cards()` returns `watchlist_hits` with watchlist display names.
- duplicate symbol hits are deduplicated.
- output order follows `primary_symbol` then `related_symbols`.
- blank `display_name` entries are skipped.
- `/api/news/feed-layout` returns `watchlist_hits` in event payloads.

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py backend/tests/test_news.py -q`
Expected: FAIL on missing `watchlist_hits` behavior.

- [ ] **Step 3: Write minimal implementation**

Modify:
- `backend/app/schemas/news.py`
- `backend/app/services/news_feed_layout.py`
- any helper imports needed for watchlist lookup

Implement:
- `watchlist_hits: list[str]` on event models
- watchlist lookup from repository/session
- compact event-card hit derivation from `primary_symbol` and `related_symbols`
- stable hit ordering and blank-name skip rules

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py backend/tests/test_news.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_news_feed_layout.py backend/tests/test_news.py backend/app/schemas/news.py backend/app/services/news_feed_layout.py
git commit -m "feat: add watchlist hits to news events"
```

## Chunk 2: Frontend Card Rendering

### Task 2: Add failing frontend tests for compact hit strip

**Files:**
- Modify: `frontend/src/api/client.test.ts`
- Modify: `frontend/src/stores/newsStore.test.ts`
- Modify: `frontend/src/components/news/EventFeedCard.test.ts`
- Modify: `frontend/src/views/NewsFeedView.test.ts`
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Write the failing tests**

Add assertions that:
- API/store path accepts `watchlist_hits` without dropping it
- event card renders `命中持仓` when `watchlist_hits` exists
- only first two names render and overflow collapses to `+N`
- no hit strip is rendered when list is empty
- feed view still renders compact event discovery and includes hit-strip copy
- hit strip stays single-line via the dedicated class hook

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/newsStore.test.ts src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts`
Expected: FAIL on missing `watchlist_hits` field/rendering.

- [ ] **Step 3: Write minimal implementation**

Modify:
- `frontend/src/api/client.test.ts`
- `frontend/src/stores/newsStore.test.ts`
- `frontend/src/components/news/EventFeedCard.vue`
- `frontend/src/types/api.ts`

Implement:
- event card computed values for visible hit names and overflow count
- compact single-line hit strip
- style adjustments that preserve current compact density
- no-op consumption path for `watchlist_hits` in API/store types

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/newsStore.test.ts src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.test.ts frontend/src/stores/newsStore.test.ts frontend/src/components/news/EventFeedCard.test.ts frontend/src/views/NewsFeedView.test.ts frontend/src/components/news/EventFeedCard.vue frontend/src/types/api.ts
git commit -m "feat: show watchlist hits on news cards"
```

## Chunk 3: Verification And Records

### Task 3: Run full targeted verification and update docs

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update change log**

Add a top entry describing the new compact watchlist-hit strip, API contract change, and verification evidence.

- [ ] **Step 2: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py -q`
Expected: PASS

- [ ] **Step 3: Run frontend verification**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/newsStore.test.ts src/components/news/EventFeedCard.test.ts src/views/NewsFeedView.test.ts`
Expected: PASS

- [ ] **Step 4: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/code-change-log.md
git commit -m "docs: record news portfolio hit strip"
```
