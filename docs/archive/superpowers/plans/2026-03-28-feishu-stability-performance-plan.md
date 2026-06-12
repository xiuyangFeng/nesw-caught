# Feishu Stability Performance Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Feishu notification delivery from fragile in-memory dispatch to a persisted, retryable backend flow with reusable HTTP/token handling and regression coverage.

**Architecture:** Add a persisted `notification_job` queue plus repository-backed delivery worker so business events enqueue jobs instead of sending directly. Keep the first implementation deliberately small: analysis and watchlist alerts enqueue delivery jobs immediately, news notifications persist durable source-event rows first and only materialize `news_batch` delivery jobs in the worker; Feishu API interaction is isolated behind a process-level reusable sender with connection pooling, token caching, and retry classification.

**Tech Stack:** FastAPI, SQLAlchemy ORM, SQLite bootstrap via initializer, pytest, httpx

---

## File Map

- Create: `backend/app/models/notification_job.py` — persisted notification queue rows for both source events and delivery tasks
- Create: `backend/app/repositories/notification_job_repository.py` — enqueue, claim, retry, mark-sent, source-event batching, and expired-lease recovery operations
- Modify: `backend/app/models/__init__.py` — register the new model
- Modify: `backend/app/db/initializer.py` — ensure any required notification job columns/indexes exist on existing databases
- Modify: `backend/app/services/feishu_client.py` — reusable process-level sender/client factory, token cache refresh, retry classification helpers
- Modify: `backend/app/services/notification_service.py` — enqueue jobs, batch due news events, delivery loop, and bounded retry scheduling
- Modify: `backend/app/main.py` — keep startup wiring aligned with the new delivery loop
- Modify: `backend/app/api/routes/notify.py` — route test-send through the reusable Feishu sender path if needed
- Create: `backend/tests/test_notification_jobs.py` — TDD coverage for persisted queue model/repository semantics
- Create: `backend/tests/test_feishu_sender.py` — TDD coverage for sender reuse, token refresh, and retry classification
- Modify: `backend/tests/test_feishu_notify.py` — integration coverage for enqueue, batching, and delivery retries
- Modify: `docs/code-change-log.md` — record the completed implementation

## Chunk 1: Persist Notification Jobs

### Task 1: Add persisted notification job model and repository

**Files:**
- Create: `backend/app/models/notification_job.py`
- Create: `backend/app/repositories/notification_job_repository.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/db/initializer.py`
- Test: `backend/tests/test_notification_jobs.py`

- [ ] **Step 1: Write the failing tests for notification jobs**

```python
def test_enqueue_analysis_job_persists_pending_notification():
    ...

def test_enqueue_news_source_event_persists_pending_batch_input():
    ...

def test_claim_due_jobs_marks_rows_sending_with_lease():
    ...

def test_claim_due_jobs_reclaims_expired_sending_lease():
    ...

def test_mark_job_retry_applies_backoff_and_error():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run: `conda run -n news-caught pytest backend/tests/test_notification_jobs.py -q`
Expected: FAIL because `NotificationJob` / repository operations do not exist yet.

- [ ] **Step 3: Implement the minimal model, repository, and DB bootstrap support**

```python
class NotificationJob(Base):
    __tablename__ = "notification_job"
    ...

class NotificationJobRepository:
    def enqueue(...)
    def enqueue_news_source_event(...)
    def claim_due_jobs(...)
    def list_due_news_source_events(...)
    def mark_news_events_batched(...)
    def mark_sent(...)
    def mark_retry(...)
```

- [ ] **Step 4: Re-run the targeted tests to verify GREEN**

Run: `conda run -n news-caught pytest backend/tests/test_notification_jobs.py -q`
Expected: PASS for the new repository/model cases.

## Chunk 2: Delivery Worker and Feishu Sender Reuse

### Task 2: Add reusable Feishu sender and bounded retry classification

**Files:**
- Modify: `backend/app/services/feishu_client.py`
- Test: `backend/tests/test_feishu_sender.py`

- [ ] **Step 1: Write the failing tests for sender reuse and error classification**

```python
def test_feishu_sender_reuses_cached_token_until_refresh_buffer():
    ...

def test_get_shared_feishu_sender_reuses_http_client_for_same_credentials():
    ...

def test_feishu_sender_retries_once_after_token_invalid():
    ...

def test_feishu_error_classifier_marks_config_errors_non_retryable():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run: `conda run -n news-caught pytest backend/tests/test_feishu_sender.py -q`
Expected: FAIL because token/provider reuse and retryability helpers are missing.

- [ ] **Step 3: Implement the minimal reusable sender path**

```python
class FeishuSender:
    def send_card(...)
    def send_test(...)

def get_shared_feishu_sender(...)

def classify_feishu_error(...)
```

- [ ] **Step 4: Re-run the targeted tests to verify GREEN**

Run: `conda run -n news-caught pytest backend/tests/test_feishu_sender.py -q`
Expected: PASS for the new sender tests.

### Task 3: Move notification service to persisted enqueue + delivery loop

**Files:**
- Modify: `backend/app/services/notification_service.py`
- Test: `backend/tests/test_feishu_notify.py`

- [ ] **Step 1: Write the failing tests for persisted delivery flow**

```python
def test_analysis_completion_enqueues_job_instead_of_sending_inline():
    ...

def test_watchlist_alert_enqueues_once_per_threshold_crossing():
    ...

def test_news_events_batch_into_single_card_when_window_is_due():
    ...

def test_delivery_loop_retries_retryable_failures_and_marks_sent_after_success():
    ...

def test_delivery_loop_reclaims_expired_sending_jobs_after_worker_restart():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run: `conda run -n news-caught pytest backend/tests/test_feishu_notify.py -q`
Expected: FAIL because `NotificationService` still uses in-memory buffer/direct send.

- [ ] **Step 3: Implement the minimal enqueue and delivery logic**

```python
class NotificationService:
    def on_news_created(...): enqueue source event
    def on_watchlist_alert(...): enqueue immediate alert job
    def on_analysis_completed(...): enqueue immediate analysis job
    def _batch_due_news_events(...): materialize batch jobs
    def _delivery_tick(...): claim, send, mark sent/retry
```

- [ ] **Step 4: Re-run the targeted tests to verify GREEN**

Run: `conda run -n news-caught pytest backend/tests/test_feishu_notify.py -q`
Expected: PASS for enqueue, batching, and retry flow tests.

### Task 4: Wire startup and route-level send path to the reusable sender

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/routes/notify.py`
- Test: `backend/tests/test_feishu_notify.py`

- [ ] **Step 1: Write the failing route/startup tests**

```python
def test_test_feishu_notification_uses_shared_sender():
    ...

def test_notification_service_start_stop_preserves_single_delivery_thread():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run: `conda run -n news-caught pytest backend/tests/test_feishu_notify.py -q`
Expected: FAIL because route/startup wiring still targets the old direct client path.

- [ ] **Step 3: Implement the minimal route/startup wiring**

```python
def test_feishu_notification(...): use get_shared_feishu_sender(...)
def lifespan(...): start/stop the persisted delivery worker cleanly
```

- [ ] **Step 4: Re-run the targeted tests to verify GREEN**

Run: `conda run -n news-caught pytest backend/tests/test_feishu_notify.py -q`
Expected: PASS for shared sender route and startup wiring.

## Chunk 3: Verification and Documentation

### Task 5: Run verification and document the completed change

**Files:**
- Modify: `docs/code-change-log.md`
- Modify: `backend/tests/test_feishu_notify.py`

- [ ] **Step 1: Run the focused backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_feishu_notify.py -q`
Expected: PASS

- [ ] **Step 2: Run adjacent backend regression coverage**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_market.py -q`
Expected: PASS

- [ ] **Step 3: Update the code change log with the implementation facts**

```md
## YYYY-MM-DD HH:MM
- 修改范围：...
- 变更内容：...
```

- [ ] **Step 4: Run the combined backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_feishu_notify.py backend/tests/test_news_ingestion.py backend/tests/test_market.py -q`
Expected: PASS
