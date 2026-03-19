# X Monitor Translation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add on-demand Chinese translation for each X Monitor post while keeping the existing external-link flow unchanged.

**Architecture:** Add a backend `POST /api/llm/translate` endpoint backed by the existing active LLM provider configuration and expose it through the frontend API client. Store per-post translation state in the X Monitor Pinia store so the page can render button/loading/error/success states without persisting anything across refreshes.

**Tech Stack:** FastAPI, SQLAlchemy repository pattern, existing OpenAI-compatible LLM provider wrapper, Vue 3, Pinia, Vitest, pytest

---

## Chunk 1: Backend Translation API

### Task 1: Add backend contract and failing route tests

**Files:**
- Modify: `backend/app/api/routes/llm.py`
- Modify: `backend/app/services/llm_providers.py`
- Modify: `backend/app/schemas/llm.py`
- Modify: `backend/tests/test_news_analysis.py`

- [ ] **Step 1: Write the failing schema and route tests**

Add tests covering:
- `POST /api/llm/translate` returns `400` when no active provider exists
- `POST /api/llm/translate` returns `400` for empty or oversized text
- `POST /api/llm/translate` returns translated text and active provider metadata when provider succeeds
- `POST /api/llm/translate` returns `502` when provider returns an empty translation

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_analysis.py -q -k translate`
Expected: FAIL because the route/schema/provider method do not exist yet

- [ ] **Step 3: Add the request/response schemas**

Implement translation request/response models in `backend/app/schemas/llm.py`.

- [ ] **Step 4: Add the provider text-generation method**

Implement a plain-text generation method in `backend/app/services/llm_providers.py` for translation prompts.

- [ ] **Step 5: Add the route handler**

Implement `POST /api/llm/translate` in `backend/app/api/routes/llm.py`.

- [ ] **Step 6: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_news_analysis.py -q -k translate`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/llm.py backend/app/api/routes/llm.py backend/app/services/llm_providers.py backend/tests/test_news_analysis.py
git commit -m "feat: add llm translation endpoint"
```

## Chunk 2: Frontend Translation State and View

### Task 2: Add frontend API types and failing X Monitor view test

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/client.test.ts`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 1: Write the failing frontend test**

Add tests covering:
- each X Monitor post shows a `翻译` button
- clicking `翻译` calls the store action and renders returned translated text
- failed translation shows a per-post error message
- search-result cards also show `翻译` and can render translated text
- feed items and search items do not collide even when their `id` values are reused

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: FAIL because the translation API/store/view state does not exist yet

- [ ] **Step 3: Write minimal implementation scaffolding**

Add:
- translation request/response types
- mock fallback translation response

- [ ] **Step 4: Add and verify the frontend client call**

Add:
- `apiClient.translateText(...)`
- focused test coverage in `frontend/src/api/client.test.ts` for backend call and offline fallback

- [ ] **Step 5: Run test to verify partial failures remain focused**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: Still FAIL, now only because the store/view logic has not been added yet

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/api/client.ts frontend/src/api/mock.ts frontend/src/views/XMonitorView.test.ts
git commit -m "test: add x monitor translation view coverage"
```

### Task 3: Implement X Monitor translation store and UI

**Files:**
- Modify: `frontend/src/stores/xMonitorStore.ts`
- Modify: `frontend/src/views/XMonitorView.vue`
- Test: `frontend/src/views/XMonitorView.test.ts`

- [ ] **Step 1: Implement translation key helper and translation state model**

Add a store map keyed by a stable `translationKey` with:
- `idle`/`loading`/`success`/`error`
- `translated_text`
- `error`

Key rule:
- prefer `canonical_url`
- otherwise use `${account_handle}:${posted_at ?? captured_at}:${content_text}`

- [ ] **Step 2: Implement the `translatePost(postId, text)` action**

Expose a `translatePost(postId, text)` action that:
- skips empty text
- skips duplicate in-flight requests
- reuses existing successful translation within the same session
- updates state based on API result

- [ ] **Step 3: Render translation controls for the monitored post feed**

Update the monitored post list to:
- show `翻译` button
- show loading/error/success states from the store
- keep `打开原帖` link unchanged

- [ ] **Step 4: Render translation controls for the search result list**

Update the search result cards to:
- show `翻译` button
- show loading/error/success states from the store
- keep `打开原帖` link unchanged

- [ ] **Step 5: Run the focused frontend tests**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts src/views/XMonitorView.test.ts`
Expected: PASS

- [ ] **Step 6: Refactor only if needed**

Keep the view readable by extracting tiny helpers/computed calls only if the template becomes noisy.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/xMonitorStore.ts frontend/src/views/XMonitorView.vue frontend/src/views/XMonitorView.test.ts
git commit -m "feat: add x monitor post translation ui"
```

## Chunk 3: Verification and Records

### Task 4: Full verification and changelog update

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_news_analysis.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run: `npm --prefix frontend run test -- --run src/views/XMonitorView.test.ts`
Expected: PASS

- [ ] **Step 3: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Update code change log**

Add a new top entry summarizing:
- new translation endpoint
- per-post translation button and session cache
- verification commands run

- [ ] **Step 5: Commit**

```bash
git add docs/code-change-log.md docs/superpowers/specs/2026-03-19-x-monitor-translation-design.md docs/superpowers/plans/2026-03-19-x-monitor-translation-plan.md
git commit -m "docs: record x monitor translation feature"
```
