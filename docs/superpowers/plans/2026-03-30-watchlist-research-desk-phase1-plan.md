# Watchlist Research Desk Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a structured research brief to watchlist detail pages so recent related news is compressed into driver categories, action levels, and a price-move-explained signal.

**Architecture:** Add a backend `watchlist research` service that reuses the existing related-news dataset, derives deterministic driver summaries, exposes them through a new watchlist route, then renders the result in the watchlist detail page through store-managed frontend state. Keep the first version rule-based and make the store own detail-page loading orchestration so the view does not duplicate news requests.

**Tech Stack:** FastAPI, SQLAlchemy repositories, Pydantic, Vue 3, Pinia, Vitest

---

## Chunk 1: Backend Research Brief API

### Task 1: Add failing backend tests for research brief generation

**Files:**
- Create: `backend/tests/test_watchlist_research.py`
- Modify: `docs/code-change-log.md`
- Test: `backend/tests/test_watchlist_research.py`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- research brief groups related news into policy/product/supply-chain/price-action categories
- action level follows the fixed 14-day window rules
- abnormal quote with no strong drivers sets `has_unexplained_price_move`
- A-share alias lookup works for `SH600519`
- route behavior is covered in `backend/tests/test_watchlist_research.py`

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_watchlist_research.py backend/tests/test_stock_news_search.py -q`
Expected: FAIL because research brief service/route/schema do not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement:
- research brief schemas in `backend/app/schemas/watchlist.py`
- `backend/app/services/watchlist_research_service.py`
- `GET /api/watchlist/{symbol}/research-brief` in `backend/app/api/routes/watchlist.py`
- append `docs/code-change-log.md` for this completed backend unit

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_watchlist_research.py backend/tests/test_stock_news_search.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/watchlist.py backend/app/services/watchlist_research_service.py backend/app/api/routes/watchlist.py backend/tests/test_watchlist_research.py docs/code-change-log.md
git commit -m "feat: add watchlist research brief api"
```

## Chunk 2: Frontend API and Store State

### Task 2: Add failing frontend tests for API client and store state

**Files:**
- Modify: `frontend/src/stores/watchlistStore.ts`
- Modify: `frontend/src/stores/watchlistStore.test.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/client.test.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- API client can fetch `/api/watchlist/{symbol}/research-brief`
- store loads and stores research brief separately from raw related news
- detail-page load orchestration lives in store, not view, to avoid duplicate news requests

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/watchlistStore.test.ts`
Expected: FAIL because new API/store wiring does not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement:
- API types and client method
- mock fallback data
- store state + `loadResearchBrief`
- store-owned detail workspace loader that coordinates quote, chart, related news, and research brief
- append `docs/code-change-log.md` for this completed frontend state unit

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/watchlistStore.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/watchlistStore.ts frontend/src/stores/watchlistStore.test.ts frontend/src/types/api.ts frontend/src/api/client.ts frontend/src/api/client.test.ts frontend/src/api/mock.ts docs/code-change-log.md
git commit -m "feat: add watchlist research brief state"
```

## Chunk 3: Frontend Panel and Detail Integration

### Task 3: Add failing UI tests and render the research brief

**Files:**
- Create: `frontend/src/components/watchlist/ResearchBriefPanel.vue`
- Create: `frontend/src/components/watchlist/ResearchBriefPanel.test.ts`
- Modify: `frontend/src/components/watchlist/StockDetailPanel.vue`
- Modify: `frontend/src/components/watchlist/StockDetailPanel.test.ts`
- Modify: `frontend/src/views/WatchlistDetailView.vue`
- Modify: `frontend/src/views/WatchlistDetailView.test.ts`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Write the failing tests**

Add tests that prove:
- `ResearchBriefPanel` shows top action level, category groups, and empty fallback copy
- `StockDetailPanel` renders research brief between chart summary and raw news
- detail page calls the single store-owned workspace loader instead of manually duplicating news loads
- detail page still stays on-page when research brief fails

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/ResearchBriefPanel.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
Expected: FAIL because panel and single-loader integration do not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement:
- `ResearchBriefPanel.vue`
- `StockDetailPanel.vue` integration
- `WatchlistDetailView.vue` switched to the single store loader
- append `docs/code-change-log.md` for this completed UI unit

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm --prefix frontend run test -- --run src/components/watchlist/ResearchBriefPanel.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/watchlist/ResearchBriefPanel.vue frontend/src/components/watchlist/ResearchBriefPanel.test.ts frontend/src/components/watchlist/StockDetailPanel.vue frontend/src/components/watchlist/StockDetailPanel.test.ts frontend/src/views/WatchlistDetailView.vue frontend/src/views/WatchlistDetailView.test.ts docs/code-change-log.md
git commit -m "feat: render watchlist research brief"
```

## Chunk 4: Full Verification

### Task 4: Run end-to-end verification for the planned scope

**Files:**
- Modify: none expected

- [ ] **Step 1: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_watchlist_research.py backend/tests/test_stock_news_search.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/stores/watchlistStore.test.ts src/components/watchlist/ResearchBriefPanel.test.ts src/components/watchlist/StockDetailPanel.test.ts src/views/WatchlistDetailView.test.ts`
Expected: PASS

- [ ] **Step 3: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Review against spec**

Check the implementation against `docs/superpowers/specs/2026-03-30-watchlist-research-desk-phase1-design.md` and confirm:
- deterministic research brief exists
- four driver classes are covered
- action levels are shown
- research brief failure does not block detail page
