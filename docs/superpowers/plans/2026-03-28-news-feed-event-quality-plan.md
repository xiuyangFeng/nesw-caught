# News Feed Event Quality Improvement Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve news feed event quality by adding Chinese sentiment/event_type support, source tier weighting, time decay, and N+1 query fix — all backend-only, no frontend changes.

**Architecture:** Modify 4 backend files: `news_signal_classifier.py` (Chinese sentiment + tokenizer), `news_feed_layout.py` (Chinese event types + source weighting + time decay + N+1 fix), `topic_repository.py` (batch queries), and tests. No schema changes, no frontend changes, no new dependencies.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest

**Design doc:** `docs/superpowers/specs/2026-03-28-news-feed-event-quality-design.md`

---

## Chunk 1: Chinese Sentiment & Tokenizer

### Task 1: Add Chinese sentiment support to classifier

**Files:**
- Modify: `backend/app/services/news_signal_classifier.py`
- Modify: `backend/tests/test_news_signal_pipeline.py`
- Test: `backend/tests/test_news_signal_pipeline.py`

- [ ] **Step 1: Write failing tests for Chinese sentiment**

Add tests that verify:
- Chinese positive title (e.g. "营收大涨超预期") → `sentiment_label == "positive"`
- Chinese negative title (e.g. "股价暴跌 市场承压") → `sentiment_label == "negative"`
- Mixed Chinese+English title → combined scoring works
- Chinese text with no sentiment words → `neutral`
- Chinese theme words contribute to `topic_key`

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Chinese sentiment**

In `news_signal_classifier.py`:
- Add `POSITIVE_ZH`, `NEGATIVE_ZH`, `THEME_ZH` dicts
- Add `_zh_tokens(self, text)` method — scan text for predefined Chinese terms (longest-match-first)
- Extend `_tokenize` to return `en_tokens + zh_tokens`
- Update `_topic_key` to recognize Chinese theme terms

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/news_signal_classifier.py backend/tests/test_news_signal_pipeline.py
git commit -m "feat: add Chinese sentiment and tokenizer to signal classifier"
```

---

## Chunk 2: Chinese Event Type Patterns + Source Weighting + Time Decay

### Task 2: Add Chinese event_type, source weighting, and time decay to feed layout

**Files:**
- Modify: `backend/app/services/news_feed_layout.py`
- Modify: `backend/tests/test_news_feed_layout.py`
- Test: `backend/tests/test_news_feed_layout.py`

- [ ] **Step 1: Write failing tests**

Add tests that verify:
- Chinese keywords "财报" / "营收" → `event_type == "earnings"`
- Chinese keywords "监管" / "处罚" → `event_type == "regulation"`
- Chinese keywords "大涨" / "暴跌" → `event_type == "market_move"`
- Primary source event gets higher importance than fallback source event
- Recent event sorts before older event with same base importance
- 24h-old event has roughly halved decayed importance

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -v`
Expected: FAIL

- [ ] **Step 3: Implement changes**

In `news_feed_layout.py`:
- Extend `EVENT_TYPE_PATTERNS` with Chinese keywords per type
- Add `SOURCE_TIER_WEIGHTS` dict and `_source_weight_map()` helper
- Add `_decayed_importance()` function with exponential decay (λ=0.03)
- Update `build_event_cards()` to apply source weighting and decay-based sorting
- Import `load_sources` for source_name → tier lookup

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/news_feed_layout.py backend/tests/test_news_feed_layout.py
git commit -m "feat: Chinese event types, source weighting, time decay for feed layout"
```

---

## Chunk 3: N+1 Query Fix

### Task 3: Replace per-topic queries with batch queries

**Files:**
- Modify: `backend/app/repositories/topic_repository.py`
- Modify: `backend/app/services/news_feed_layout.py`
- Modify: `backend/tests/test_news_feed_layout.py`
- Test: `backend/tests/test_news_feed_layout.py`

- [ ] **Step 1: Write failing test for batch query correctness**

Add a test that creates 3+ topics with news, calls `feed-layout`, and verifies:
- All topics return correct news items
- All topics return correct related symbols
- Market filter works correctly in batch mode

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -v`
Expected: FAIL (if testing new batch methods directly)

- [ ] **Step 3: Implement batch queries**

In `topic_repository.py`:
- Add `batch_news_for_topics(topic_ids)` → `dict[int, list[NewsItem]]`
- Add `batch_related_symbols(topic_ids, market)` → `dict[int, list[str]]`

In `news_feed_layout.py`:
- Replace loop with `batch_news_for_topics` + `batch_related_symbols`

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_feed_layout.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/topic_repository.py backend/app/services/news_feed_layout.py backend/tests/test_news_feed_layout.py
git commit -m "perf: replace N+1 queries with batch queries in feed layout"
```

---

## Chunk 4: Verification & Project Record

### Task 4: Full regression + change log

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run full backend regression**

Run: `conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_feed_layout.py backend/tests/test_news_signal_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 2: Run frontend build check**

Run: `npm --prefix frontend run build`
Expected: PASS (no frontend changes, just verify no breakage)

- [ ] **Step 3: Update change log**

Append entry to `docs/code-change-log.md` covering all changes.

- [ ] **Step 4: Commit**

```bash
git add docs/code-change-log.md docs/superpowers/specs/2026-03-28-news-feed-event-quality-design.md docs/superpowers/plans/2026-03-28-news-feed-event-quality-plan.md
git commit -m "docs: record event quality improvement work"
```

---

Plan complete. Execution proceeds in subagent-driven mode.
