# Auto Signal And Topic Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically classify sentiment and cluster topics for newly inserted news after each refresh.

**Architecture:** Add a synchronous post-refresh backend pipeline that processes only newly inserted news. The pipeline uses rule-based sentiment/topic assignment as the baseline, optionally refines low-confidence items and new topics with LLM output, and persists reusable signal metadata plus topic links in the database.

**Tech Stack:** FastAPI, SQLAlchemy, Python, pytest

---

## Chunk 1: Data Model And Pipeline Test Coverage

### Task 1: Add failing tests for rule sentiment classification and topic assignment

**Files:**
- Create: `backend/tests/test_news_signal_pipeline.py`
- Modify: `backend/app/services/news_ingestion.py`
- Modify: `backend/app/db/initializer.py`

- [ ] **Step 1: Write the failing tests**

Add tests that:
- create inserted news items and assert the pipeline classifies them as `positive`, `negative`, or `neutral`
- assert similar news items are linked into the same topic
- assert a dissimilar news item creates a new topic
- assert LLM failure still leaves rule-based sentiment/topic results persisted

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py -q`
Expected: FAIL because the pipeline and persistence model do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add the new signal result model/repository hooks plus the minimal pipeline services needed to satisfy the tests and wire refresh to invoke them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py -q`
Expected: PASS

## Chunk 2: Topic API And Refresh Integration Regression Coverage

### Task 2: Add failing integration tests for topic API output after refresh

**Files:**
- Modify: `backend/tests/test_news_ingestion.py`
- Modify: `backend/tests/test_news.py`
- Modify: `backend/app/api/routes/topics.py`
- Modify: `backend/app/repositories/topic_repository.py`

- [ ] **Step 1: Write the failing tests**

Add tests that:
- verify refresh triggers the pipeline for inserted items
- verify newly processed topics appear in `/api/topics`
- verify `GET /api/news/{id}` returns the linked topic for processed news
- verify seeded/demo topics do not block new automatic topic creation

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_news.py -q`
Expected: FAIL because refresh does not yet trigger the new pipeline behavior.

- [ ] **Step 3: Write minimal implementation**

Update refresh orchestration and repository queries so topic APIs surface automatically generated clusters and linked news consistently.

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_news.py -q`
Expected: PASS

## Chunk 3: Records And Verification

### Task 3: Update records and run focused verification

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update the code change log**

Add a top entry describing the automatic signal/topic pipeline, affected files, validation, and residual risks.

- [ ] **Step 2: Run focused backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py backend/tests/test_news_ingestion.py backend/tests/test_news.py -q`
Expected: PASS

- [ ] **Step 3: Run full backend verification**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS
