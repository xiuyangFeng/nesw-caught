# Newsfeed Source Realtime Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production slice of the newsfeed source-governance and realtime pipeline so backend source health/runtime data and incremental news events reach the existing frontend feed reliably.

**Architecture:** Extend the backend ingestion layer with explicit source-registry metadata, market-scoped health/runtime aggregation, and single-item realtime events that flow through the existing stream layer. Keep the frontend change set narrow: reuse the current global SSE connection, add `news.updated` handling and news runtime polling in `newsStore`, and upgrade `NewsFeedView` with a minimal top status band instead of a full diagnostics panel.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Pinia, Vue 3, Vitest, pytest

---

## File Map

- Modify: `backend/app/services/news_ingestion.py`
  Purpose: source registry metadata defaults/migration, market-scoped health updates, `news.created` publish path.
- Modify: `backend/app/db/initializer.py`
  Purpose: source health schema migration/backfill for existing local databases.
- Modify: `backend/app/models/source_health.py`
  Purpose: change source health uniqueness/scope from source-only to source+market.
- Modify: `backend/app/repositories/source_health_repository.py`
  Purpose: per-market lookup/update helpers.
- Create: `backend/app/services/news_runtime.py`
  Purpose: dedicated runtime aggregation service for `GET /api/news/runtime`.
- Modify: `backend/app/schemas/source_health.py`
  Purpose: runtime/source health response schema additions.
- Modify: `backend/app/api/routes/news.py`
  Purpose: add `GET /api/news/runtime`.
- Modify: `backend/app/api/routes/stream.py`
  Purpose: add `/api/stream/events` SSE endpoint or extend existing stream route to forward incremental events.
- Modify: `backend/app/main.py`
  Purpose: register any new event forwarding/pipeline handlers cleanly.
- Modify: `backend/app/services/event_bus.py`
  Purpose: if needed, expose subscription/forwarding helpers for SSE stream consumption.
- Modify: `backend/tests/test_news_ingestion.py`
  Purpose: source metadata migration/defaults, per-market health behavior, publish semantics.
- Modify: `backend/tests/test_news.py`
  Purpose: runtime API contract coverage.
- Modify: `backend/data/news_sources.example.json`
  Purpose: document the new registry shape in example config.
- Create or Modify: `backend/tests/test_stream_events.py`
  Purpose: incremental stream forwarding for `news.created` and `news.updated`.
- Modify: `frontend/src/types/api.ts`
  Purpose: news runtime types and `news.updated` stream event contract.
- Modify: `frontend/src/api/client.ts`
  Purpose: `getNewsRuntime()` client method.
- Modify: `frontend/src/api/mock.ts`
  Purpose: news runtime degraded fallback payload.
- Create or Modify: `frontend/src/api/client.test.ts`
  Purpose: verify `getNewsRuntime()` client behavior directly.
- Modify: `frontend/src/stores/newsStore.ts`
  Purpose: runtime polling state, `news.updated` handling, scoped eviction rules.
- Modify: `frontend/src/components/layout/AppShell.vue`
  Purpose: dispatch `news.updated` events to `newsStore`.
- Modify: `frontend/src/components/layout/AppShell.test.ts`
  Purpose: verify stream routing for `news.updated`.
- Modify: `frontend/src/views/NewsFeedView.vue`
  Purpose: minimal top status band driven by news runtime + connection state.
- Modify: `frontend/src/stores/newsStore.test.ts`
  Purpose: incremental update/eviction/runtime tests.
- Modify: `frontend/src/views/NewsFeedView.test.ts`
  Purpose: status band rendering and degraded/delayed/live messaging.
- Modify: `docs/code-change-log.md`
  Purpose: record each completed implementation unit.

## Chunk 1: Backend Source Registry And Runtime Contract

### Task 1: Lock the source registry shape with tests

**Files:**
- Modify: `backend/tests/test_news_ingestion.py`
- Modify: `backend/app/services/news_ingestion.py`

- [ ] **Step 1: Write the failing tests for source config migration defaults and validation**

```python
def test_load_sources_backfills_registry_defaults_from_legacy_config(tmp_path, monkeypatch):
    config = tmp_path / "sources.json"
    config.write_text(json.dumps({
        "sources": [
            {
                "name": "Legacy Feed",
                "source_type": "rss",
                "url": "https://example.com/rss",
                "market": "us",
            }
        ]
    }), encoding="utf-8")

    monkeypatch.setenv("NEWS_SOURCES_FILE", str(config))
    sources = load_sources()

    legacy = next(item for item in sources if item.name == "Legacy Feed")
    assert legacy.tier == "primary"
    assert legacy.priority == 100
    assert legacy.cadence_seconds == 300
    assert legacy.markets == ["us"]
    assert legacy.supports_incremental is False

def test_load_sources_rejects_invalid_registry_values(tmp_path, monkeypatch):
    config = tmp_path / "sources.json"
    config.write_text(json.dumps({
        "sources": [
            {
                "name": "Broken Feed",
                "source_type": "rss",
                "url": "https://example.com/rss",
                "market": "us",
                "tier": "broken",
                "priority": 0,
                "cadence_seconds": 0,
            }
        ]
    }), encoding="utf-8")
    monkeypatch.setenv("NEWS_SOURCES_FILE", str(config))
    with pytest.raises(ValueError):
        load_sources()
```

- [ ] **Step 1.5: Update the example config in the same task**

```json
{
  "name": "Example IR RSS",
  "tier": "primary",
  "priority": 10,
  "cadence_seconds": 300,
  "markets": ["us"]
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_load_sources_backfills_registry_defaults_from_legacy_config backend/tests/test_news_ingestion.py::test_load_sources_rejects_invalid_registry_values -q`
Expected: FAIL because `SourceDefinition`/`load_sources()` do not expose the new fields or validation yet.

- [ ] **Step 3: Write minimal implementation for source registry defaults and validation**

```python
@dataclass(frozen=True)
class SourceDefinition:
    ...
    tier: str = "primary"
    priority: int = 100
    cadence_seconds: int = 300
    markets: list[str] | None = None
    supports_incremental: bool = False
    quality_weight: float = 0.5
```

```python
def _hydrate_source_defaults(raw: dict[str, object]) -> dict[str, object]:
    market = raw.get("market")
    return {
        **raw,
        "tier": raw.get("tier", "primary"),
        "priority": raw.get("priority", 100),
        "cadence_seconds": raw.get("cadence_seconds", 300),
        "markets": raw.get("markets") or ([market] if market else []),
        "supports_incremental": raw.get("supports_incremental", False),
        "quality_weight": raw.get("quality_weight", 0.5),
    }

def _validate_source_definition(source: SourceDefinition) -> None:
    if source.tier not in {"primary", "secondary", "fallback"}:
        raise ValueError("invalid tier")
    if source.priority <= 0:
        raise ValueError("priority must be positive")
    if source.cadence_seconds <= 0:
        raise ValueError("cadence_seconds must be positive")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_load_sources_backfills_registry_defaults_from_legacy_config backend/tests/test_news_ingestion.py::test_load_sources_rejects_invalid_registry_values -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_news_ingestion.py backend/app/services/news_ingestion.py backend/data/news_sources.example.json
git commit -m "feat: add news source registry defaults"
```

### Task 2: Move source health to source+market scope

**Files:**
- Modify: `backend/tests/test_news_ingestion.py`
- Modify: `backend/app/models/source_health.py`
- Modify: `backend/app/repositories/source_health_repository.py`
- Modify: `backend/app/services/news_ingestion.py`
- Modify: `backend/app/db/initializer.py`

- [ ] **Step 1: Write the failing test for market-scoped health records**

```python
def test_refresh_source_tracks_health_per_source_market_pair():
    source = SourceDefinition(
        name="Multi Market Feed",
        source_type="rss",
        url="https://example.com/rss",
        market="us",
        markets=["us", "hk"],
    )
    ...
    health_rows = SourceHealthRepository(session).list_all()
    assert {(item.source_name, item.market) for item in health_rows} == {("Multi Market Feed", "us")}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_refresh_source_tracks_health_per_source_market_pair -q`
Expected: FAIL because `SourceHealth` is source-only.

- [ ] **Step 3: Write minimal implementation and migration/backfill**

```python
class SourceHealth(Base):
    ...
    market: Mapped[str] = mapped_column(String(16), index=True)
    __table_args__ = (UniqueConstraint("source_name", "market", name="uq_source_health_source_market"),)
```

```python
def get_or_create(self, *, source_name: str, source_type: str, market: str) -> SourceHealth:
    stmt = select(SourceHealth).where(
        SourceHealth.source_name == source_name,
        SourceHealth.market == market,
    )
```

```python
def ensure_source_health_market_column() -> None:
    # add market column if missing, backfill from legacy source definitions/news_item market,
    # then recreate uniqueness expectations for source_name + market
```

- [ ] **Step 4: Run focused tests**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -q`
Expected: PASS for source health scope and no regression in ingestion helpers.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_news_ingestion.py backend/app/models/source_health.py backend/app/repositories/source_health_repository.py backend/app/services/news_ingestion.py backend/app/db/initializer.py
git commit -m "feat: scope news source health by market"
```

### Task 3: Add the news runtime API contract

**Files:**
- Modify: `backend/tests/test_news.py`
- Modify: `backend/app/schemas/source_health.py`
- Modify: `backend/app/api/routes/news.py`
- Modify: `backend/app/repositories/source_health_repository.py`
- Create: `backend/app/services/news_runtime.py`

- [ ] **Step 1: Write the failing runtime API test**

```python
def test_news_runtime_returns_market_and_source_health_contract(client, session):
    response = client.get("/api/news/runtime")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "feed_status": "live",
        "last_refresh_finished_at": "2026-03-25T02:40:00Z",
        "last_news_created_at": "2026-03-25T02:39:40Z",
        "last_incremental_event_at": "2026-03-25T02:39:40Z",
        "degraded_market_count": 0,
        "markets": [
            {
                "market": "us",
                "status": "live",
                "mode": "primary",
                "last_primary_success_at": "2026-03-25T02:39:30Z",
                "last_news_created_at": "2026-03-25T02:39:40Z",
                "degraded_reason": None,
            }
        ],
        "sources": [
            {
                "source_name": "Example Source",
                "market": "us",
                "tier": "primary",
                "status": "ok",
                "last_attempt_at": "2026-03-25T02:39:20Z",
                "last_success_at": "2026-03-25T02:39:30Z",
                "consecutive_failures": 0,
                "avg_fetch_latency_ms": 320.0,
                "latest_news_published_at": "2026-03-25T02:35:00Z",
                "latest_news_fetched_at": "2026-03-25T02:39:30Z",
                "last_error": None,
            }
        ],
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news.py::test_news_runtime_returns_market_and_source_health_contract -q`
Expected: FAIL because route/schema do not exist.

- [ ] **Step 3: Implement minimal runtime aggregation**

```python
@router.get("/runtime", response_model=NewsRuntimeView)
def get_news_runtime(...):
    return NewsRuntimeService(session, get_event_bus()).build()
```

```python
class NewsRuntimeService:
    def build(self) -> NewsRuntimeView:
        ...
```

- [ ] **Step 4: Run focused backend tests**

Run: `conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_ingestion.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_news.py backend/tests/test_news_ingestion.py backend/app/schemas/source_health.py backend/app/api/routes/news.py backend/app/repositories/source_health_repository.py backend/app/services/news_runtime.py
git commit -m "feat: add news runtime health api"
```

## Chunk 2: Incremental Event Pipeline And SSE Forwarding

### Task 4: Publish `news.created` on first insert

**Files:**
- Modify: `backend/tests/test_news_ingestion.py`
- Modify: `backend/app/services/news_ingestion.py`

- [ ] **Step 1: Write the failing event publish test**

```python
def test_refresh_all_publishes_news_created_for_each_insert(monkeypatch):
    fake_bus = FakeBus()
    monkeypatch.setattr("app.services.news_ingestion.get_event_bus", lambda: fake_bus)
    ...
    assert ("news.created", {"id": stored_id, ...}) in fake_bus.published
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_refresh_all_publishes_news_created_for_each_insert -q`
Expected: FAIL because only `news.created_batch` is published.

- [ ] **Step 3: Implement minimal publish path**

```python
if inserted_item is not None:
    event_bus.publish("news.created", NewsItemSummary.model_validate(inserted_item, from_attributes=True).model_dump())
```

- [ ] **Step 4: Run focused test**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py::test_refresh_all_publishes_news_created_for_each_insert -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_news_ingestion.py backend/app/services/news_ingestion.py
git commit -m "feat: publish incremental news created events"
```

### Task 5: Publish `news.updated` after enrichment

**Files:**
- Modify: `backend/tests/test_news_signal_pipeline.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/news_signal_pipeline.py` or the handler wrapper that already publishes `news.signals_processed`

- [ ] **Step 1: Write the failing test for enriched update event**

```python
def test_news_created_batch_handler_publishes_news_updated_after_processing(monkeypatch):
    fake_bus = FakeBus()
    ...
    assert ("news.updated", {
        "id": news_id,
        "title": "Processed headline",
        "summary": "Processed summary",
        "source_name": "Reuters",
        "market": "us",
        "published_at": "2026-03-25T02:30:00Z",
        "fetched_at": "2026-03-25T02:31:03Z",
        "sentiment_label": "positive",
        "canonical_url": "https://example.com/story",
        "updated_fields": ["sentiment_label", "summary"],
    }) in fake_bus.published
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py -q`
Expected: FAIL because no `news.updated` event exists.

- [ ] **Step 3: Implement minimal update publish at the batch handler boundary**

```python
event_bus.publish("news.updated", build_news_summary_payload(item))
```

- [ ] **Step 4: Run focused tests**

Run: `conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py backend/tests/test_news_ingestion.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_news_signal_pipeline.py backend/app/main.py backend/app/services/news_signal_pipeline.py
git commit -m "feat: publish enriched news update events"
```

### Task 6: Expose `/api/stream/events` to the existing frontend SSE client

**Files:**
- Create or Modify: `backend/tests/test_stream_events.py`
- Modify: `backend/app/api/routes/stream.py`
- Modify: `backend/app/services/event_bus.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing SSE forwarding test**

```python
def test_stream_events_forwards_news_created_and_news_updated(monkeypatch):
    fake_bus = RecordingEventBus()
    monkeypatch.setattr("app.api.routes.stream.get_event_bus", lambda: fake_bus)
    with TestClient(app) as client:
        with client.stream("GET", "/api/stream/events?limit=2") as response:
            fake_bus.publish("news.created", {"id": 1, ...})
            fake_bus.publish("news.updated", {"id": 1, ...})
            chunks = list(itertools.islice(response.iter_lines(), 6))
    body = "\n".join(chunks)
    assert '"type":"news.created"' in body
    assert '"type":"news.updated"' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_stream_events.py -q`
Expected: FAIL because `/api/stream/events` is missing or does not forward those events.

- [ ] **Step 3: Implement minimal SSE bridge with bounded test mode**

```python
@router.get("/events")
async def stream_events(limit: int | None = None):
    ...
    yield f"data: {json.dumps(envelope)}\n\n"
```

- [ ] **Step 4: Run stream-focused tests**

Run: `conda run -n news-caught pytest backend/tests/test_stream_events.py backend/tests/test_stream_status.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_stream_events.py backend/app/api/routes/stream.py backend/app/services/event_bus.py backend/app/main.py
git commit -m "feat: forward incremental news events over sse"
```

### Task 6.5: Record chunk-2 completion before moving on

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Append a factual log entry for the backend realtime event slice**

```md
## YYYY-MM-DD HH:MM
- 修改人：Codex
- 修改范围：newsfeed 增量事件与 SSE 转发
- 变更内容：记录 `news.created`、`news.updated` 和 `/api/stream/events` 这一明确修改单元
- 影响文件：列出 backend 事件与 stream 文件
- 接口/数据结构变化：列出新事件和 SSE 入口
- 验证情况：列出 chunk 2 已跑测试
- 风险/后续事项：...
```

- [ ] **Step 2: Commit the log update**

```bash
git add docs/code-change-log.md
git commit -m "docs: record news realtime event slice"
```

## Chunk 3: Frontend News Runtime And Incremental Feed Wiring

### Task 7: Extend API types and client methods

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/mock.ts`
- Create or Modify: `frontend/src/api/client.test.ts`

- [ ] **Step 1: Write the failing type/client test**

```ts
it('loads news runtime from the api client', async () => {
  server.use(http.get('/api/news/runtime', () => HttpResponse.json({ feed_status: 'live', ... })));
  const response = await apiClient.getNewsRuntime();
  expect(response.data.feed_status).toBe('live');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts`
Expected: FAIL because `getNewsRuntime()`, news runtime types, and the fallback mock payload do not exist.

- [ ] **Step 3: Implement minimal client/type additions**

```ts
export interface NewsRuntimeStatus { ... }
export interface StreamEventMap { 'news.updated': NewsItem; ... }
```

```ts
getNewsRuntime() {
  return withMockFallback<NewsRuntimeStatus>(() => getJson('/api/news/runtime'), () => mockNewsRuntimeStatus);
}
```

- [ ] **Step 4: Run focused frontend test**

Run: `npm --prefix frontend run test -- --run src/api/client.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/api/client.ts frontend/src/api/mock.ts frontend/src/api/client.test.ts
git commit -m "feat: add news runtime api client"
```

### Task 8: Add runtime polling and `news.updated` handling to `newsStore`

**Files:**
- Modify: `frontend/src/stores/newsStore.ts`
- Modify: `frontend/src/stores/newsStore.test.ts`

- [ ] **Step 1: Write the failing store tests**

```ts
it('updates an existing news item and evicts it when it no longer matches the scoped query', async () => {
  const store = useNewsStore();
  store.feedQuery = { sentiment_label: 'positive', limit: 10 };
  store.feedItems = [basePositiveItem];
  store.upsertNewsUpdate({ ...basePositiveItem, sentiment_label: 'negative' });
  expect(store.feedItems).toEqual([]);
});

it('loads news runtime into newsStore state', async () => {
  await store.loadNewsRuntime();
  expect(store.newsRuntimeStatus?.feed_status).toBe('live');
});

it('tracks lastIncrementalAt and sourceHealth from runtime data', async () => {
  await store.loadNewsRuntime();
  expect(store.sourceHealth).toHaveLength(1);
  expect(store.lastIncrementalAt).toBe('2026-03-25T02:39:40Z');
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/stores/newsStore.test.ts`
Expected: FAIL because `upsertNewsUpdate()`/runtime state do not exist.

- [ ] **Step 3: Implement minimal store changes**

```ts
async function loadNewsRuntime() { ... }
function upsertNewsUpdate(item: NewsItem) { ...remove when no longer matches... }
const lastIncrementalAt = ref<string | null>(null)
const sourceHealth = ref<NewsRuntimeSourceHealth[]>([])
```

- [ ] **Step 4: Run store tests**

Run: `npm --prefix frontend run test -- --run src/stores/newsStore.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/newsStore.ts frontend/src/stores/newsStore.test.ts
git commit -m "feat: handle news runtime and update events in store"
```

### Task 9: Wire AppShell and NewsFeedView to the new runtime/update path

**Files:**
- Modify: `frontend/src/components/layout/AppShell.vue`
- Modify: `frontend/src/components/layout/AppShell.test.ts`
- Modify: `frontend/src/views/NewsFeedView.vue`
- Modify: `frontend/src/views/NewsFeedView.test.ts`

- [ ] **Step 1: Write the failing UI tests**

```ts
it('routes news.updated events into the news store', async () => {
  ...
  emitStreamEvent({ type: 'news.updated', payload: updatedItem });
  expect(newsStore.upsertNewsUpdate).toHaveBeenCalledWith(updatedItem);
});

it('renders delayed/degraded/live status copy in the feed header', async () => {
  ...
  expect(wrapper.text()).toContain('新闻更新延迟');
  expect(wrapper.text()).toContain('最近入流');
  expect(wrapper.text()).toContain('异常来源');
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts`
Expected: FAIL because `news.updated` is not dispatched and the status band does not exist.

- [ ] **Step 3: Implement minimal UI wiring**

```ts
if (event.type === 'news.updated') {
  newsStore.upsertNewsUpdate(event.payload);
}
```

```vue
<StatusBanner
  :title="runtimeHeadline"
  :tone="runtimeTone"
  :detail="runtimeDetail"
/>
```

- [ ] **Step 4: Run focused frontend tests**

Run: `npm --prefix frontend run test -- --run src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts src/stores/newsStore.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/AppShell.vue frontend/src/components/layout/AppShell.test.ts frontend/src/views/NewsFeedView.vue frontend/src/views/NewsFeedView.test.ts
git commit -m "feat: surface news runtime status in feed"
```

## Chunk 4: Verification And Project Records

### Task 10: Full verification and final log update

**Files:**
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Run backend verification**

Run: `conda run -n news-caught pytest backend/tests/test_news.py backend/tests/test_news_ingestion.py backend/tests/test_news_signal_pipeline.py backend/tests/test_stream_events.py backend/tests/test_stream_status.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run: `npm --prefix frontend run test -- --run src/stores/newsStore.test.ts src/views/NewsFeedView.test.ts src/components/layout/AppShell.test.ts`
Expected: PASS

- [ ] **Step 3: Run build verification**

Run: `npm --prefix frontend run build`
Expected: PASS

- [ ] **Step 4: Update the code change log with verified results**

```md
## YYYY-MM-DD HH:MM

- 修改人：Codex
- 修改范围：newsfeed 数据源与实时性基础链路
- 变更内容：...
- 影响文件：
  - /Users/xiuyang/Desktop/news-caught/backend/...
  - /Users/xiuyang/Desktop/news-caught/frontend/...
- 接口/数据结构变化：...
- 验证情况：列出已通过的 pytest / vitest / build 命令
- 风险/后续事项：...
```

- [ ] **Step 5: Commit final verification record**

```bash
git add docs/code-change-log.md
git commit -m "docs: record verified newsfeed realtime slice"
```

## Chunk Review

After completing each chunk, dispatch a plan reviewer against this file and the approved spec:

- Spec: `docs/superpowers/specs/2026-03-25-newsfeed-source-realtime-design.md`
- Plan: `docs/superpowers/plans/2026-03-25-newsfeed-source-realtime-plan.md`

Stop and fix reviewer findings before moving to the next chunk.
