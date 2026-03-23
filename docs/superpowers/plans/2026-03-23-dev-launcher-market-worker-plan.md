# Dev Launcher Market Worker Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `make dev` start and clean up the market quote worker alongside backend and frontend.

**Architecture:** Extend `scripts/dev.sh` to manage a third process for `market-worker`, keep one shared cleanup path, and update README and change-log documentation to reflect the new default dev behavior.

**Tech Stack:** Bash launcher script, Makefile, pytest for script-content regression checks

---

## Chunk 1: TDD For Dev Script Behavior

### Task 1: Add failing tests for worker orchestration in the dev script

**Files:**
- Create: `backend/tests/test_dev_launcher.py`
- Modify: `scripts/dev.sh`

- [ ] **Step 1: Write failing tests**

Cover:
- `scripts/dev.sh` declares `MARKET_WORKER_PID`
- cleanup block handles `MARKET_WORKER_PID`
- script starts `python -m app.workers.market_quote_producer`

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_dev_launcher.py -q`
Expected: FAIL because the current dev script only manages backend and frontend.

- [ ] **Step 3: Implement minimal script changes**

Add the worker process, cleanup handling, and liveness checks.

- [ ] **Step 4: Re-run focused tests**

Run: `conda run -n news-caught pytest backend/tests/test_dev_launcher.py -q`
Expected: PASS.

## Chunk 2: Docs And Regression

### Task 2: Update docs and verification

**Files:**
- Modify: `README.md`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Update README**

State that `make dev` now starts backend, frontend, and market worker together.

- [ ] **Step 2: Update code change log**

Record the dev launcher behavior change and verification.

- [ ] **Step 3: Run focused verification**

Run: `conda run -n news-caught pytest backend/tests/test_dev_launcher.py -q`
Expected: PASS.

- [ ] **Step 4: Run full backend verification**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS.
