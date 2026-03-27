# Kline yfinance MultiIndex Fix Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix watchlist K-line loading so Yahoo Finance history with MultiIndex columns no longer crashes backend serialization.

**Architecture:** Keep the fix in the backend market chart service. Normalize `yfinance.download()` history frames to a stable single-level OHLCV shape before indicator and candle serialization so existing API payload contracts remain unchanged.

**Tech Stack:** FastAPI, pandas, yfinance, pytest

---

### Task 1: Add regression test for MultiIndex history frames

**Files:**
- Modify: `backend/tests/test_market.py`
- Test: `backend/tests/test_market.py`

- [ ] **Step 1: Write the failing test**

Add a test that builds a pandas DataFrame with `MultiIndex` columns shaped like `yfinance==1.2.0` output and verifies the market chart service can normalize it into scalar OHLCV columns.

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -k multiindex -q`
Expected: FAIL because current service leaves MultiIndex columns intact.

- [ ] **Step 3: Write minimal implementation**

Update `backend/app/services/market_chart_service.py` so `_download_history()` requests `multi_level_index=False` and defensively flattens any remaining MultiIndex columns to plain `Open/High/Low/Close/Adj Close/Volume`.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -k multiindex -q`
Expected: PASS.

### Task 2: Verify end-to-end K-line behavior and document the change

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run focused regression checks**

Run: `conda run -n news-caught pytest backend/tests/test_market.py -q`
Expected: PASS.

- [ ] **Step 2: Run real K-line smoke check**

Run a Python one-liner that calls `MarketChartService().get_kline('HK0700', '1d', '6mo', session)` against the local DB.
Expected: returns payload with non-zero candle count and no exception.

- [ ] **Step 3: Update change log**

Append a new top entry in `docs/code-change-log.md` with the bug root cause, fix scope, verification commands, and any residual risk.
