# X Monitor Account Management Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert X Monitor account management from file-synced read-only configuration into a database-backed management workflow with page-level CRUD plus explicit file import/export.

**Architecture:** Keep the current X Monitor product surface, but make `x_account` the runtime source of truth. Add backend account-management endpoints, retain the JSON file only for explicit import/export, and extend the existing page/store to manage accounts and tiered filtering without changing the existing post/search flows.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, Pinia, TypeScript, Vitest

---

## Chunk 1: Lock Backend Account Management Behavior

### Task 1: Add failing backend tests for account CRUD and import/export

**Files:**
- Modify: `backend/tests/test_x_monitor.py`
- Test: `backend/tests/test_x_monitor.py`

- [ ] **Step 1: Write failing tests for runtime account CRUD**

Add tests covering:
- `GET /api/x/accounts` returns ordered rows with new `tier` and `source` fields
- `POST /api/x/accounts` creates a new account with normalized handle and default `tier=watch`
- `PATCH /api/x/accounts/{handle}` updates `display_name`, `tier`, `priority`, `is_active`, `notes`
- `DELETE /api/x/accounts/{handle}` removes the account

- [ ] **Step 2: Run the targeted backend tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'account' -q`
Expected: FAIL because CRUD routes and tier fields do not exist.

- [ ] **Step 3: Write failing tests for file import/export**

Add tests covering:
- explicit import reads the account file and upserts rows
- import is merge-only and does not delete DB-only rows
- import returns `created_count`, `updated_count`, `skipped_count`
- imported rows are marked `source=file_import`
- refresh does not repopulate deleted rows from file automatically
- explicit export writes the current database state back to the configured JSON file in stable order
- refresh fetch ordering prefers `core` before `watch` and excludes `muted`

- [ ] **Step 4: Run the targeted backend tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'import or export or refresh' -q`
Expected: FAIL because import/export routes and new refresh semantics do not exist.

## Chunk 2: Implement Backend Persistence and API

### Task 2: Extend the account model, repository, schemas, and routes

**Files:**
- Modify: `backend/app/db/initializer.py`
- Modify: `backend/app/models/x_account.py`
- Modify: `backend/app/repositories/x_account_repository.py`
- Modify: `backend/app/schemas/x_monitor.py`
- Modify: `backend/app/api/routes/x_monitor.py`
- Modify: `backend/app/services/x_monitor.py`
- Test: `backend/tests/test_x_monitor.py`

- [ ] **Step 1: Add the failing model-facing tests if needed**

If route tests are not enough to drive the shape, add focused repository/service assertions for:
- tier defaulting
- handle normalization
- active account selection excluding `muted`

- [ ] **Step 2: Implement minimal account model and repository support**

Add:
- `tier`
- `source`
- repository helpers for create, update, delete, import upsert, and ordered listing

- [ ] **Step 3: Add database compatibility support**

In `backend/app/db/initializer.py`, add a compatibility helper that backfills missing `x_account.tier` and `x_account.source` columns for existing databases.

- [ ] **Step 4: Implement account CRUD endpoints**

Add:
- `POST /api/x/accounts`
- `PATCH /api/x/accounts/{handle}`
- `DELETE /api/x/accounts/{handle}`

- [ ] **Step 5: Run targeted backend tests**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -k 'account' -q`
Expected: PASS

### Task 3: Implement explicit file import/export and new refresh semantics

**Files:**
- Modify: `backend/app/services/x_monitor.py`
- Modify: `backend/app/api/routes/x_monitor.py`
- Modify: `backend/app/repositories/x_account_repository.py`
- Test: `backend/tests/test_x_monitor.py`

- [ ] **Step 1: Implement explicit import/export service methods**

Add:
- `import_accounts_from_file()`
- `export_accounts_to_file()`
- merge-only import semantics
- stable export ordering
- import result statistics

- [ ] **Step 2: Remove implicit file sync from refresh**

Change refresh so it uses database active accounts only, and excludes `muted` tier by default.

- [ ] **Step 3: Add import/export endpoints**

Add:
- `POST /api/x/accounts/import`
- `POST /api/x/accounts/export`

- [ ] **Step 4: Run focused backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -q`
Expected: PASS

## Chunk 3: Lock Frontend Account Management UX

### Task 4: Add failing frontend tests for account management UI

**Files:**
- Modify: `frontend/src/views/XMonitorView.test.ts`
- Test: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 1: Write failing tests for account CRUD interactions**

Add tests asserting the page can:
- render account tiers
- render accounts loaded from `GET /api/x/accounts`
- submit a new account
- edit account fields except `handle`
- toggle active state
- delete an account
- trigger import/export actions
- default post filtering respects the current tier model

- [ ] **Step 2: Run the targeted frontend test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: FAIL because the page has no management controls.

## Chunk 4: Implement Frontend Store and View

### Task 5: Extend API client, store, and page for account management

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/stores/xMonitorStore.ts`
- Modify: `frontend/src/views/XMonitorView.vue`
- Test: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 1: Add API types and client calls**

Add request/response types and client methods for:
- load account list with `tier` and `source`
- create account
- update account
- delete account
- import accounts
- export accounts

- [ ] **Step 2: Extend the Pinia store**

Add state and actions for:
- form editing
- account mutations
- import/export actions
- tier filter support

- [ ] **Step 3: Update the X Monitor page**

Add:
- account creation form
- tier badges/selectors
- active toggle
- delete action
- import/export buttons

- [ ] **Step 4: Run targeted frontend verification**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: PASS

### Task 6: Run broader project verification and update docs

**Files:**
- Modify: `docs/code-change-log.md`
- Modify: `README.md` only if X Monitor usage text needs adjustment

- [ ] **Step 1: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: PASS

- [ ] **Step 3: Run frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Update code change log**

Add a top entry to `docs/code-change-log.md` describing:
- database-backed account management
- explicit file import/export
- tiered account handling
- tests run and residual risks

- [ ] **Step 5: Run final focused verification**

Run: `conda run -n news-caught pytest backend/tests/test_x_monitor.py -q && npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts && npm --prefix frontend run build`
Expected: PASS
