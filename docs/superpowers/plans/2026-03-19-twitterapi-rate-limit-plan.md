# TwitterAPI.io Rate Limit Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a configurable minimum provider request interval and verify real `MiniMax_AI` posts can be fetched under a 6-second request cadence.

**Architecture:** Extend `TwitterApiIoClient` with a small in-process throttle guard driven by settings, cover it with targeted tests, then run a real provider smoke test that prints raw provider-derived post fields for `MiniMax_AI`.

**Tech Stack:** Python, httpx, pytest

---

## Chunk 1: Lock throttle behavior

### Task 1: Add failing client throttle tests

**Files:**
- Modify: `backend/tests/test_x_monitor.py`

- [ ] **Step 1: Add a test that requires sleeping when the interval is not yet satisfied**
- [ ] **Step 2: Add a test that skips sleeping when the interval is already satisfied**
- [ ] **Step 3: Run targeted tests to verify they fail**

## Chunk 2: Implement provider throttling

### Task 2: Add configurable request interval support

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/twitterapi_io_client.py`
- Modify: `.env`

- [ ] **Step 1: Add `TWITTERAPI_IO_MIN_INTERVAL_SECONDS` setting**
- [ ] **Step 2: Implement in-process throttle before each real request**
- [ ] **Step 3: Set local `.env` to 6 seconds**
- [ ] **Step 4: Run targeted throttle tests**

## Chunk 3: Verify with real provider

### Task 3: Run regression and real `MiniMax_AI` smoke test

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run `conda run -n news-caught pytest backend/tests -q`**
- [ ] **Step 2: Run a real two-request smoke test spaced by client throttle**
- [ ] **Step 3: Record the real returned `MiniMax_AI` post fields and elapsed timing**
- [ ] **Step 4: Update `docs/code-change-log.md`**
