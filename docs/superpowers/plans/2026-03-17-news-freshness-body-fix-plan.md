# News Freshness And Body Fix Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure supported news sources expose real article bodies and publication times, and make the app refresh and display the newest news instead of stale database snapshots.

**Architecture:** Extend backend ingestion with a MiniMax detail-page parser and persistence path for article content plus real publication date, tighten list ordering to prefer source publication time, and add frontend fallback/refresh behavior so the UI surfaces the newest available timestamps. Keep the change bounded to the news ingestion and news bootstrap flows.

**Tech Stack:** FastAPI, SQLAlchemy, BeautifulSoup, Vue 3, Pinia, Vitest-ready frontend, pytest backend tests

---

## Chunk 1: Backend Ingestion

### Task 1: Add failing tests for MiniMax detail parsing and recent ordering

**Files:**
- Modify: `backend/tests/test_news_ingestion.py`
- Modify: `backend/tests/test_news.py`

- [ ] **Step 1: Write the failing parser test**

Add a test that feeds a MiniMax detail HTML payload into a new parser helper and asserts:
- `published_at` parses from `ArticleTitle.props.date`
- `content_text` contains正文
- `summary` is populated from正文前缀

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q`
Expected: FAIL because the parser/helper does not exist yet.

- [ ] **Step 3: Write the failing ordering test**

Add an API-level or repository-level test proving records with newer `published_at` should come before older records even if `fetched_at` is older.

- [ ] **Step 4: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news.py -q`
Expected: FAIL because current ordering is `fetched_at desc`.

### Task 2: Implement MiniMax detail extraction

**Files:**
- Modify: `backend/app/services/news_ingestion.py`

- [ ] **Step 1: Add a MiniMax detail parser**

Implement a helper that extracts from the detail HTML:
- title
- date
- article body payload/text

- [ ] **Step 2: Thread detail fetching into MiniMax ingestion**

When source parser is `anchor_list_html` for MiniMax, fetch each new detail page, then persist:
- `NewsItem.published_at`
- `ArticleContent.content_text`
- `ArticleContent.content_html`
- `ArticleContent.extract_status`

- [ ] **Step 3: Record explicit failure state when detail extraction fails**

Persist `ArticleContent(extract_status='failed', extract_error=...)` for supported detail extraction failures so the UI no longer reports `not_requested`.

- [ ] **Step 4: Run focused tests**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q`
Expected: PASS.

### Task 3: Implement publication-time-first ordering

**Files:**
- Modify: `backend/app/repositories/news_repository.py`

- [ ] **Step 1: Change recent list ordering**

Order by:
- `published_at desc nulls last`
- `fetched_at desc`

- [ ] **Step 2: Run backend ordering tests**

Run: `conda run -n news-caught pytest backend/tests/test_news.py -q`
Expected: PASS.

## Chunk 2: Frontend Freshness Behavior

### Task 4: Add failing frontend tests or minimal behavior checks for time fallback if practical

**Files:**
- Modify: `frontend/src/utils/time.ts`
- Optionally modify: `frontend/src/utils/newsEditorial.test.ts`

- [ ] **Step 1: Add a minimal failing test if the existing frontend test setup can cover time fallback**

Assert that when `published_at` is missing the UI helper uses `fetched_at`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix frontend run test -- --run`
Expected: FAIL on the new fallback expectation, if test coverage is added.

### Task 5: Implement UI time fallback and startup refresh

**Files:**
- Modify: `frontend/src/utils/time.ts`
- Modify: `frontend/src/components/layout/AppShell.vue`
- Modify: `frontend/src/stores/newsStore.ts`
- Modify: any news views/components that directly format `published_at`

- [ ] **Step 1: Add a shared timestamp fallback helper**

Use `published_at ?? fetched_at` everywhere news time is displayed.

- [ ] **Step 2: Add a refresh API client call if missing**

Expose `/api/news/refresh` in the frontend client.

- [ ] **Step 3: Trigger one non-blocking refresh during app bootstrap**

After initial load or in bootstrap flow:
- call refresh
- reload news/topics on success
- tolerate failure without breaking page render

- [ ] **Step 4: Run frontend tests/build**

Run: `npm --prefix frontend run test -- --run`
Expected: PASS.

Run: `npm --prefix frontend run build`
Expected: PASS.

## Chunk 3: Verification And Record

### Task 6: End-to-end verification and records

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

- [ ] **Step 3: Smoke-test ingestion against live MiniMax**

Run: `make ingest-news`
Expected: newly ingested MiniMax rows have non-null `published_at` and corresponding `article_content`.

- [ ] **Step 4: Update change log**

Add one top entry to `docs/code-change-log.md` summarizing the fix, touched files, verification evidence, and residual risks.
