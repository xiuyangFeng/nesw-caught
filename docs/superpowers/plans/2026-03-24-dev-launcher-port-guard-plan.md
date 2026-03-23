# Dev Launcher Port Guard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/dev.sh` automatically clear conflicting local dev ports and block until the backend is actually reachable before leaving frontend exposed.

**Architecture:** Keep the existing bash launcher, but add focused helpers for port cleanup, early-process-exit detection, and backend readiness polling. Validate the launcher contract with script-content tests first, then implement the minimal shell changes.

**Tech Stack:** Bash, `lsof`, `curl`, pytest

---

## Chunk 1: Launcher Contract

### Task 1: Add failing launcher expectations

**Files:**
- Modify: `backend/tests/test_dev_launcher.py`
- Test: `backend/tests/test_dev_launcher.py`

- [ ] **Step 1: Write the failing test**

```python
def test_dev_script_cleans_conflicting_ports_and_waits_for_backend() -> None:
    script = Path(".../scripts/dev.sh").read_text(encoding="utf-8")

    assert "kill_listeners_for_port()" in script
    assert 'kill_listeners_for_port 8000' in script
    assert 'kill_listeners_for_port 5174' in script
    assert "wait_for_http()" in script
    assert 'wait_for_http "http://127.0.0.1:8000/api/stream/status"' in script
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_dev_launcher.py -q`
Expected: FAIL because the current script has no port cleanup or backend readiness wait

- [ ] **Step 3: Write minimal implementation**

Update `scripts/dev.sh` to add the helper functions and invoke them before and after backend startup.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_dev_launcher.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_dev_launcher.py scripts/dev.sh
git commit -m "fix: harden dev launcher startup"
```

### Task 2: Document and verify the launcher change

**Files:**
- Modify: `README.md`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Write the failing documentation expectation**

Manual expectation: README should explain that `make dev` now clears stale local dev listeners on `8000` and `5174` before startup.

- [ ] **Step 2: Update docs minimally**

Add a short note to `README.md` and append a factual entry to `docs/code-change-log.md`.

- [ ] **Step 3: Verify**

Run:
- `conda run -n news-caught pytest backend/tests/test_dev_launcher.py -q`
- `conda run -n news-caught pytest backend/tests -q`

Expected: PASS
