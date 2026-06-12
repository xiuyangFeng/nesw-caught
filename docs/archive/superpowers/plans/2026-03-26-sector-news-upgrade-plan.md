# Sector News Upgrade Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal sector-oriented source and filtering upgrade for Hong Kong and U.S. market monitoring.

**Architecture:** Extend the existing ingestion pipeline with an `api` source type, keep source tier metadata available for ranking, add lightweight duplicate suppression during refresh, and enrich the relevance evaluator with deterministic sector tagging. Keep the implementation narrow and test-driven so the existing research benchmark flow remains usable.

**Tech Stack:** FastAPI backend, SQLAlchemy ORM, pytest, httpx, JSON source registry, existing research schemas/services.

---

## Chunk 1: Ingestion Extensions

### Task 1: Add `api` source registry and fetch support

**Files:**
- Modify: `backend/app/services/news_ingestion.py`
- Modify: `backend/tests/test_news_ingestion.py`

- [ ] **Step 1: Write the failing test**

Add tests proving:

- `load_sources()` accepts `source_type="api"`
- API source definitions require an API-specific parser identifier
- refresh can normalize a JSON payload into `SourceItem` records

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k 'api_source' -q`
Expected: FAIL because `api` sources are not supported yet.

- [ ] **Step 3: Write minimal implementation**

Implement:

- `SourceType = Literal["rss", "html", "api"]`
- API source config fields needed for first-pass fetching
- a narrow JSON parser for The News API style payloads
- ingestion fetch handling that reuses existing normalization/storage logic

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k 'api_source' -q`
Expected: PASS.

### Task 2: Add lightweight duplicate suppression during refresh

**Files:**
- Modify: `backend/app/services/news_ingestion.py`
- Modify: `backend/tests/test_news_ingestion.py`

- [ ] **Step 1: Write the failing test**

Add a test proving refresh skips a same-window near-duplicate with a different URL but matching normalized title and host signature.

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k 'duplicate_signature' -q`
Expected: FAIL because refresh currently only deduplicates on canonical URL.

- [ ] **Step 3: Write minimal implementation**

Implement:

- normalized duplicate signature helper
- same-window duplicate lookup during refresh
- narrow update behavior that does not overwrite unrelated rows

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k 'duplicate_signature' -q`
Expected: PASS.

## Chunk 2: Sector Tagging and Ranking

### Task 3: Add sector tagging alongside market relevance prediction

**Files:**
- Modify: `backend/app/services/news_relevance_evaluator.py`
- Modify: `backend/tests/test_news_relevance_evaluator.py`

- [ ] **Step 1: Write the failing test**

Add tests proving:

- AI/compute headlines tag `ai_compute`
- semiconductor export-control headlines tag `semiconductors`
- Chinese internet regulatory/earnings headlines tag `chinese_internet`
- Apple supply-chain headlines tag `apple_supply_chain`

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'sector_tag' -q`
Expected: FAIL because sector metadata is not returned yet.

- [ ] **Step 3: Write minimal implementation**

Implement:

- deterministic sector keyword groups
- a metadata-returning prediction helper
- `predict_market_relevance()` as a compatibility wrapper over the richer helper

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'sector_tag' -q`
Expected: PASS.

### Task 4: Add ranking helper for sector-oriented surfacing

**Files:**
- Create: `backend/app/services/news_priority.py`
- Create: `backend/tests/test_news_priority.py`

- [ ] **Step 1: Write the failing test**

Add tests proving:

- primary sector-tagged stories outrank secondary generic stories
- official filing/regulatory stories outrank media rewrites with similar timestamps

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_priority.py -q`
Expected: FAIL because the ranking helper does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement a small pure-Python ranking helper that scores:

- source tier
- sector tag presence
- official source/relevance reason hints
- recency

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_news_priority.py -q`
Expected: PASS.

## Chunk 3: Regression and Documentation

### Task 5: Verify touched backend paths and update records

**Files:**
- Modify: `docs/code-change-log.md`
- Modify: `docs/superpowers/specs/2026-03-26-sector-news-upgrade-design.md`
- Modify: `docs/superpowers/plans/2026-03-26-sector-news-upgrade-plan.md`

- [ ] **Step 1: Run targeted regression suite**

Run:

- `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_priority.py -q`

Expected: PASS.

- [ ] **Step 2: Run broader verification for touched flows**

Run:

- `conda run -n news-caught pytest backend/tests/test_news_relevance_report.py backend/tests/test_news_signal_pipeline.py backend/tests/test_news.py -q`
- `conda run -n news-caught python -m py_compile backend/app/services/news_ingestion.py backend/app/services/news_relevance_evaluator.py backend/app/services/news_priority.py`

Expected: PASS.

- [ ] **Step 3: Update documentation and change log**

Add a new top entry to `docs/code-change-log.md` with changed files, verification commands, and residual risks.

- [ ] **Step 4: Final review checklist**

Verify:

- no unsupported source types remain undocumented
- compatibility wrappers still support existing benchmark scripts
- ranking helper is isolated and deterministic
- docs reflect the actual first-iteration scope
