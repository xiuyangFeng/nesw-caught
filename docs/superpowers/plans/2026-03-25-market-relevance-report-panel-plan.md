# Market Relevance Report Panel Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate Markdown and HTML report panels for the market relevance autoresearch workflow from existing benchmark and evaluation artifacts.

**Architecture:** Add one backend reporting service that loads benchmark, evaluation, and ledger artifacts and renders two read-only outputs. Expose it through one thin CLI so both humans and automations can refresh the panel without touching the evaluation logic.

**Tech Stack:** Python, pytest, existing backend research artifact files, inline HTML/CSS

---

## Chunk 1: Reporting Service

### Task 1: Add failing report aggregation and rendering tests

**Files:**
- Create: `backend/tests/test_news_relevance_report.py`
- Create: `backend/app/services/news_relevance_report.py`

- [ ] **Step 1: Write failing tests for report aggregation**

Cover:
- loading evaluation metrics and benchmark counts
- resolving false positive / false negative ids back to sample titles
- rendering Markdown with metrics and error buckets
- rendering HTML with the same core sections

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_report.py -q`
Expected: FAIL because the report service does not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement a report service with:
- artifact loading
- compact report dataclasses
- Markdown renderer
- HTML renderer

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_report.py -q`
Expected: PASS

### Task 2: Add a CLI that writes both report files

**Files:**
- Create: `backend/scripts/render_market_relevance_report.py`
- Modify: `backend/tests/test_news_relevance_report.py`

- [ ] **Step 1: Write a failing CLI test**

Add a test that runs the script against fixture artifacts and expects both `.md` and `.html` outputs.

- [ ] **Step 2: Run the targeted tests to verify the CLI test fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_report.py -q`
Expected: FAIL because the script does not exist yet

- [ ] **Step 3: Write the minimal CLI**

The script should accept explicit input and output paths, load the report service, and write both files.

- [ ] **Step 4: Re-run the tests**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_report.py -q`
Expected: PASS

## Chunk 2: Produce Real Artifacts And Document Them

### Task 3: Render the current report panel from real repo artifacts

**Files:**
- Create: `backend/data/research/market_relevance_report.md`
- Create: `backend/data/research/market_relevance_report.html`

- [ ] **Step 1: Run the report CLI against current repo artifacts**

Run: `conda run -n news-caught python backend/scripts/render_market_relevance_report.py --benchmark backend/data/research/market_relevance_benchmark.jsonl --evaluation backend/data/research/market_relevance_baseline/evaluation.json --ledger docs/research/market-relevance-experiments.tsv --markdown-output backend/data/research/market_relevance_report.md --html-output backend/data/research/market_relevance_report.html`

- [ ] **Step 2: Verify both files are created**

Check that both outputs exist and contain the current metric values.

### Task 4: Update code-change-log and verify the slice

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Record the report panel change**

Add a top entry describing the new report service, CLI, artifacts, and verification.

- [ ] **Step 2: Run the final verification slice**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_report.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q`

- [ ] **Step 3: Run py_compile on the new files**

Run: `conda run -n news-caught python -m py_compile backend/app/services/news_relevance_report.py backend/scripts/render_market_relevance_report.py`
