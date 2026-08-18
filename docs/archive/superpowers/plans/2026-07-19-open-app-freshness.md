# 打开 App 即时刷新 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打开 App 时立即（异步、非阻塞）触发一次全源新闻抓取，并在前台停留期间周期性补抓，让用户回到项目时总能看到接近实时的新闻，而不需要常驻后台调度器。

**Architecture:** 后端刷新链路（`POST /api/news/refresh?async_mode=true` → `NewsIngestionService.refresh_all()` 并发抓取 → 落库 → 发布 `news.created`/`news.created_batch` 事件）已经完整存在，不做任何改动。本计划只改前端三处：(1) `apiClient.refreshNews()` 改用异步模式；(2) `newsStore` 增加 `isRefreshing` 状态，刷新语义从"等响应体里的结果"改为"依赖后续 SSE `news.created` 事件清除指示器"；(3) `AppShell.vue` 在挂载时立即触发一次刷新，并新增页面可见性感知的周期性补抓定时器 + 一个轻量"同步中"指示器。

**Tech Stack:** Vue 3 + `<script setup>` + Pinia（前端），Vitest + `@vue/test-utils`（测试）。后端 FastAPI 接口保持不变，仅作为既有依赖使用。

## Global Constraints

- 不改动后端任何文件（`backend/`），后台常驻调度器 `news_scheduler_enabled` 保持默认关闭。
- 手动/自动刷新共用同一条 60 秒冷却（客户端 `REFRESH_COOLDOWN_MS` + 服务端 lease），本计划不改变冷却时长。
- 刷新触发后不再依赖响应体做整页数据重载；新增条目一律走既有 SSE `news.created` → `newsStore.upsertNews` 增量路径。
- "同步中"指示器的兜底超时为 15 秒（`REFRESHING_INDICATOR_TIMEOUT_MS`），无论是否收到新条目都要清除，避免卡死显示。
- 前台周期性补抓间隔为 5 分钟（`newsRefreshPollIntervalMs = 5 * 60_000`），仅在 `document.visibilityState === 'visible'` 时运行，隐藏时暂停，重新可见时立即补发一次并重启计时器。

---

## File Structure

- `frontend/src/types/api.ts` —— 新增手写类型 `NewsRefreshAcceptedResult`（`async_mode=true` 分支的响应体，OpenAPI 的 `NewsRefreshResponse` 只覆盖同步分支，不适用）。
- `frontend/src/api/client.ts` —— `refreshNews()` 改为请求 `?async_mode=true`，返回类型改为 `NewsRefreshAcceptedResult`。
- `frontend/src/api/client.test.ts` —— 补一条断言：请求 URL 带 `async_mode=true`。
- `frontend/src/stores/newsStore.ts` —— 新增 `isRefreshing` ref 与 `clearRefreshingIndicator()`；`refreshDashboardNews()` 语义改为"触发即返回，不再等结果重载列表"；`upsertNews()` 收到新条目时清除指示器。
- `frontend/src/stores/newsStore.test.ts` —— 更新受影响的既有用例（响应体形状、不再断言 `loadDashboardNews` 被调用），新增 `isRefreshing` 状态流转用例。
- `frontend/src/components/layout/AppShell.vue` —— `bootstrap()` 内立即触发一次刷新；新增可见性感知的周期性刷新定时器；模板内新增"同步中"指示器。
- `frontend/src/components/layout/AppShell.test.ts` —— 更新"不自动触发刷新"的既有用例为"挂载时触发一次"；新增周期性刷新 + 可见性暂停/恢复 + 指示器渲染的用例。

---

## Task 1: 类型与 apiClient 改为异步刷新模式

**Files:**
- Modify: `frontend/src/types/api.ts:45`（在 `NewsRefreshResult` 之后新增类型）
- Modify: `frontend/src/api/client.ts:224-226`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces: `NewsRefreshAcceptedResult = { status: string; message: string }`（`frontend/src/types/api.ts`），`apiClient.refreshNews(): Promise<{ data: NewsRefreshAcceptedResult; degraded: false }>`（`frontend/src/api/client.ts`）——供 Task 2 的 `newsStore.refreshDashboardNews()` 使用。

- [ ] **Step 1: 在 `types/api.ts` 新增异步刷新响应类型**

在 `frontend/src/types/api.ts` 第 45 行（`export type NewsRefreshResult = Schemas['NewsRefreshResponse'];`）之后插入：

```ts
// 前端 UI 专用:POST /api/news/refresh?async_mode=true 分支返回的是手工拼装的
// JSONResponse({"status": "accepted", "message": ...}),不是 response_model
// 声明的 NewsRefreshResponse(那是同步分支的形状),OpenAPI 不覆盖,手写。
export interface NewsRefreshAcceptedResult {
  status: string;
  message: string;
}
```

- [ ] **Step 2: 改写 `apiClient.refreshNews()` 使用 async_mode**

打开 `frontend/src/api/client.ts`。在顶部 import 列表（第 27 行 `NewsRefreshResult,`）之后新增一行导入 `NewsRefreshAcceptedResult`：

```ts
  NewsRefreshResult,
  NewsRefreshAcceptedResult,
```

将第 224-226 行：

```ts
  refreshNews() {
    return postJson<NewsRefreshResult>('/api/news/refresh', {}).then((data) => ({ data, degraded: false }));
  },
```

替换为：

```ts
  refreshNews() {
    return postJson<NewsRefreshAcceptedResult>(withQuery('/api/news/refresh', { async_mode: true }), {}).then(
      (data) => ({ data, degraded: false }),
    );
  },
```

（`withQuery` 与 `NewsRefreshResult` 已在文件顶部导入；`NewsRefreshResult` 若无其他引用处使用可保留 import，不必删除，避免影响其他潜在引用。先用 `grep -n "NewsRefreshResult" frontend/src -r` 确认没有其他文件引用它，若确无引用可以从 import 中移除该行以保持整洁。）

- [ ] **Step 3: 补充 client 测试断言 URL 带 async_mode**

打开 `frontend/src/api/client.test.ts`，在文件末尾 `describe('apiClient write operations'` 块内、`afterEach` 之后新增一条测试：

```ts
  it('requests an async-mode refresh so the scrape runs as a background task', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({ status: 'accepted', message: 'News refresh started in background' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.refreshNews();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/news/refresh?async_mode=true',
      expect.objectContaining({ method: 'POST' }),
    );
  });
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: 全部用例 PASS，包括新增的 async_mode 断言。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/api/client.ts frontend/src/api/client.test.ts
git commit -m "feat(frontend): news refresh 请求改为 async_mode 异步刷新"
```

---

## Task 2: `newsStore` 增加 `isRefreshing` 状态并改写刷新语义

**Files:**
- Modify: `frontend/src/stores/newsStore.ts:299-326`（冷却常量与 `refreshDashboardNews`）、`:328-335`（`upsertNews`）、`:345-391`（导出列表）
- Test: `frontend/src/stores/newsStore.test.ts`

**Interfaces:**
- Consumes: `apiClient.refreshNews(): Promise<{ data: NewsRefreshAcceptedResult; degraded: boolean }>`（Task 1）。
- Produces: `newsStore.isRefreshing: Ref<boolean>`，`newsStore.refreshDashboardNews(): Promise<boolean>`（返回值语义不变：`true`=已成功触发本轮刷新，`false`=冷却中/降级/请求失败），`newsStore.refreshNews()`（不变，仍是 `refreshDashboardNews` 的别名）——供 Task 3 的 `AppShell.vue` 调用与渲染。

- [ ] **Step 1: 改写冷却区块，新增 `isRefreshing` 与清除函数**

打开 `frontend/src/stores/newsStore.ts`。将第 299-326 行：

```ts
  const REFRESH_COOLDOWN_MS = 60_000;
  let lastManualRefreshAt = 0;

  async function refreshNews() {
    return refreshDashboardNews();
  }

  async function refreshDashboardNews() {
    const now = Date.now();
    if (now - lastManualRefreshAt < REFRESH_COOLDOWN_MS) {
      return false;
    }
    try {
      const response = await apiClient.refreshNews();
      usingMock.value = usingMock.value || response.degraded;
      if (response.degraded) {
        return false;
      }

      lastManualRefreshAt = Date.now();
      await loadDashboardNews(dashboardQuery.value);
      return true;
    } catch {
      // Refresh is a background convenience; callers only need success/failure.
      // Do not start cooldown on failure so the user can retry immediately.
      return false;
    }
  }
```

替换为：

```ts
  const REFRESH_COOLDOWN_MS = 60_000;
  const REFRESHING_INDICATOR_TIMEOUT_MS = 15_000;
  let lastManualRefreshAt = 0;
  let refreshingTimeoutHandle: ReturnType<typeof setTimeout> | null = null;
  const isRefreshing = ref(false);

  function clearRefreshingIndicator() {
    isRefreshing.value = false;
    if (refreshingTimeoutHandle !== null) {
      clearTimeout(refreshingTimeoutHandle);
      refreshingTimeoutHandle = null;
    }
  }

  async function refreshNews() {
    return refreshDashboardNews();
  }

  async function refreshDashboardNews() {
    const now = Date.now();
    if (now - lastManualRefreshAt < REFRESH_COOLDOWN_MS) {
      return false;
    }
    try {
      const response = await apiClient.refreshNews();
      usingMock.value = usingMock.value || response.degraded;
      if (response.degraded) {
        return false;
      }

      lastManualRefreshAt = Date.now();
      isRefreshing.value = true;
      if (refreshingTimeoutHandle !== null) {
        clearTimeout(refreshingTimeoutHandle);
      }
      refreshingTimeoutHandle = setTimeout(() => {
        refreshingTimeoutHandle = null;
        isRefreshing.value = false;
      }, REFRESHING_INDICATOR_TIMEOUT_MS);
      return true;
    } catch {
      // Refresh is a background convenience; callers only need success/failure.
      // Do not start cooldown on failure so the user can retry immediately.
      return false;
    }
  }
```

（`refresh_all()` 现在只是"抓取已触发"的信号，真正的抓取结果通过 SSE `news.created` 事件异步到达，因此不再调用 `loadDashboardNews` 整页重载。）

- [ ] **Step 2: `upsertNews` 收到新条目时清除同步指示器**

将第 328-335 行：

```ts
  function upsertNews(item: NewsItem) {
    upsertScopedItems(dashboardItems, dashboardQuery.value, item);
    upsertScopedItems(feedItems, feedQuery.value, item);
    upsertScopedItems(sentimentItems, sentimentQuery.value, item);
    upsertLayoutStream(item);
    dashboardLastLoadedAt.value = new Date().toISOString();
    feedLastLoadedAt.value = new Date().toISOString();
  }
```

替换为：

```ts
  function upsertNews(item: NewsItem) {
    upsertScopedItems(dashboardItems, dashboardQuery.value, item);
    upsertScopedItems(feedItems, feedQuery.value, item);
    upsertScopedItems(sentimentItems, sentimentQuery.value, item);
    upsertLayoutStream(item);
    dashboardLastLoadedAt.value = new Date().toISOString();
    feedLastLoadedAt.value = new Date().toISOString();
    clearRefreshingIndicator();
  }
```

- [ ] **Step 3: 在返回对象中导出 `isRefreshing`**

在第 345-391 行的返回对象中，找到 `usingMock,`（第 351 行）这一行，紧随其后新增一行 `isRefreshing,`：

```ts
    usingMock,
    isRefreshing,
```

- [ ] **Step 4: 更新既有测试以匹配新的响应体形状与语义**

打开 `frontend/src/stores/newsStore.test.ts`。

第一处，将：

```ts
  it('does not start cooldown when refresh request fails', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.refreshNews
      .mockRejectedValueOnce(new Error('backend offline'))
      .mockResolvedValueOnce({
        data: { status: 'ok', results: [] },
        degraded: false,
      });
    apiClient.getNews.mockResolvedValue({
      data: { items: [], next_cursor: null },
      degraded: false,
    });

    await expect((store as any).refreshDashboardNews()).resolves.toBe(false);
    await expect((store as any).refreshDashboardNews()).resolves.toBe(true);
    expect(apiClient.refreshNews).toHaveBeenCalledTimes(2);
  });
```

替换为：

```ts
  it('does not start cooldown when refresh request fails', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.refreshNews
      .mockRejectedValueOnce(new Error('backend offline'))
      .mockResolvedValueOnce({
        data: { status: 'accepted', message: 'News refresh started in background' },
        degraded: false,
      });

    await expect((store as any).refreshDashboardNews()).resolves.toBe(false);
    await expect((store as any).refreshDashboardNews()).resolves.toBe(true);
    expect(apiClient.refreshNews).toHaveBeenCalledTimes(2);
  });
```

第二处，将：

```ts
  it('enforces a cooldown between manual full-source refreshes', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-17T12:00:00Z'));
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.refreshNews.mockResolvedValue({
      data: { status: 'ok', results: [] },
      degraded: false,
    });
    apiClient.getNews.mockResolvedValue({
      data: { items: [], next_cursor: null },
      degraded: false,
    });

    await expect((store as any).refreshDashboardNews()).resolves.toBe(true);
    await expect((store as any).refreshDashboardNews()).resolves.toBe(false);
    expect(apiClient.refreshNews).toHaveBeenCalledTimes(1);

    vi.setSystemTime(new Date('2026-07-17T12:01:01Z'));
    await expect((store as any).refreshDashboardNews()).resolves.toBe(true);
    expect(apiClient.refreshNews).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
```

替换为：

```ts
  it('enforces a cooldown between manual full-source refreshes', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-17T12:00:00Z'));
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.refreshNews.mockResolvedValue({
      data: { status: 'accepted', message: 'News refresh started in background' },
      degraded: false,
    });

    await expect((store as any).refreshDashboardNews()).resolves.toBe(true);
    await expect((store as any).refreshDashboardNews()).resolves.toBe(false);
    expect(apiClient.refreshNews).toHaveBeenCalledTimes(1);

    vi.setSystemTime(new Date('2026-07-17T12:01:01Z'));
    await expect((store as any).refreshDashboardNews()).resolves.toBe(true);
    expect(apiClient.refreshNews).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
```

- [ ] **Step 5: 新增 `isRefreshing` 状态流转测试**

在 `frontend/src/stores/newsStore.test.ts` 文件末尾（最后一个 `it(...)` 块之后、`});` 收尾的 `describe` 结束括号之前）新增：

```ts
  it('sets isRefreshing on a successful trigger and clears it when a news.created upsert arrives', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.refreshNews.mockResolvedValue({
      data: { status: 'accepted', message: 'News refresh started in background' },
      degraded: false,
    });

    await (store as any).refreshDashboardNews();
    expect((store as any).isRefreshing).toBe(true);

    (store as any).upsertNews({
      id: 42,
      title: 'Fresh headline',
      summary: 'Fresh summary',
      source_name: 'Reuters',
      canonical_url: 'https://example.com/fresh-42',
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-07-19T02:30:00Z',
      fetched_at: '2026-07-19T02:31:00Z',
    });

    expect((store as any).isRefreshing).toBe(false);
  });

  it('clears isRefreshing after the safety timeout when no new item arrives', async () => {
    vi.useFakeTimers();
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.refreshNews.mockResolvedValue({
      data: { status: 'accepted', message: 'News refresh started in background' },
      degraded: false,
    });

    await (store as any).refreshDashboardNews();
    expect((store as any).isRefreshing).toBe(true);

    await vi.advanceTimersByTimeAsync(15_000);

    expect((store as any).isRefreshing).toBe(false);
    vi.useRealTimers();
  });

  it('does not set isRefreshing when the refresh request fails', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.refreshNews.mockRejectedValue(new Error('backend offline'));

    await (store as any).refreshDashboardNews();
    expect((store as any).isRefreshing).toBe(false);
  });
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/stores/newsStore.test.ts`
Expected: 全部用例 PASS（含 3 条新增用例与 2 条改写用例）。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/newsStore.ts frontend/src/stores/newsStore.test.ts
git commit -m "feat(frontend): newsStore 新增 isRefreshing 同步指示器状态"
```

---

## Task 3: `AppShell.vue` 挂载即触发刷新 + 前台周期性补抓 + 同步指示器

**Files:**
- Modify: `frontend/src/components/layout/AppShell.vue`
- Test: `frontend/src/components/layout/AppShell.test.ts`

**Interfaces:**
- Consumes: `newsStore.refreshDashboardNews(): Promise<boolean>`、`newsStore.isRefreshing: boolean`（Task 2）。

- [ ] **Step 1: 新增周期性刷新的状态与时间常量**

打开 `frontend/src/components/layout/AppShell.vue`。在第 29 行 `const feedLayoutPollIntervalMs = 60_000;` 之后新增一行：

```ts
const newsRefreshPollIntervalMs = 5 * 60_000;
```

在第 31 行 `let feedLayoutPollHandle: ReturnType<typeof setInterval> | null = null;` 之后新增一行：

```ts
let newsRefreshPollHandle: ReturnType<typeof setInterval> | null = null;
```

- [ ] **Step 2: 新增触发/启停/可见性处理函数**

在第 256 行 `startFeedLayoutPolling` 函数结束的 `}` 之后（即 `reconcileNewsSnapshot` 函数定义之前）插入：

```ts
function triggerNewsRefresh() {
  if (shellDisposed) {
    return;
  }
  void newsStore.refreshDashboardNews();
}

function stopNewsRefreshPolling() {
  if (newsRefreshPollHandle === null) {
    return;
  }
  clearInterval(newsRefreshPollHandle);
  newsRefreshPollHandle = null;
}

function startNewsRefreshPolling() {
  stopNewsRefreshPolling();
  newsRefreshPollHandle = setInterval(triggerNewsRefresh, newsRefreshPollIntervalMs);
}

function handleVisibilityChange() {
  if (shellDisposed) {
    return;
  }
  if (document.visibilityState === 'visible') {
    triggerNewsRefresh();
    startNewsRefreshPolling();
  } else {
    stopNewsRefreshPolling();
  }
}
```

- [ ] **Step 3: `bootstrap()` 挂载时立即触发一次刷新，并启动周期轮询 + 可见性监听**

将第 274-330 行的 `bootstrap` 函数开头：

```ts
async function bootstrap() {
  await runtimeStatusStore.loadRuntimeStatus();
```

替换为：

```ts
async function bootstrap() {
  triggerNewsRefresh();
  await runtimeStatusStore.loadRuntimeStatus();
```

再将同一函数内（第 292-293 行）：

```ts
  startRuntimeStatusPolling();
  startFeedLayoutPolling();
```

替换为：

```ts
  startRuntimeStatusPolling();
  startFeedLayoutPolling();
  startNewsRefreshPolling();
  document.addEventListener('visibilitychange', handleVisibilityChange);
```

- [ ] **Step 4: 卸载时清理定时器与事件监听**

将第 337-346 行的 `onBeforeUnmount`：

```ts
onBeforeUnmount(() => {
  shellDisposed = true;
  if (feedLayoutDebounceHandle !== null) {
    clearTimeout(feedLayoutDebounceHandle);
    feedLayoutDebounceHandle = null;
  }
  stopFeedLayoutPolling();
  stopRuntimeStatusPolling();
  connectionStore.disconnect();
});
```

替换为：

```ts
onBeforeUnmount(() => {
  shellDisposed = true;
  if (feedLayoutDebounceHandle !== null) {
    clearTimeout(feedLayoutDebounceHandle);
    feedLayoutDebounceHandle = null;
  }
  stopFeedLayoutPolling();
  stopRuntimeStatusPolling();
  stopNewsRefreshPolling();
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  connectionStore.disconnect();
});
```

- [ ] **Step 5: 模板内新增"同步中"指示器**

在模板中找到第 486-487 行：

```html
          {{ shellStatusRail.label }}
          </span>
          <span class="text-[10px] uppercase tracking-[0.16em] text-text-faint">{{ shellStatusRail.detail }}</span>
```

替换为（新增一个 `v-if` 指示器，紧跟在 detail 后面）：

```html
          {{ shellStatusRail.label }}
          </span>
          <span class="text-[10px] uppercase tracking-[0.16em] text-text-faint">{{ shellStatusRail.detail }}</span>
          <span
            v-if="newsStore.isRefreshing"
            class="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-accent"
            data-role="news-refresh-indicator"
          >
            <span
              class="h-1.5 w-1.5 rounded-full bg-accent pulse-dot"
              style="--pulse-color: color-mix(in srgb, var(--accent) 35%, transparent)"
            />
            同步中
          </span>
```

（注意：原第 486-487 行前还有一个 `</span>` 收尾（对应第 474 行开始的外层 `span`）——原文件里第 485 行是 `{{ shellStatusRail.label }}`，第 486 行是该外层 `span` 的收尾 `</span>`，第 487 行才是 `shellStatusRail.detail` 的 `span`。请以 Read 工具重新核对当前行号后再定位替换范围，不要凭行号盲改；用字符串匹配 `{{ shellStatusRail.detail }}</span>` 定位插入点最可靠。）

- [ ] **Step 6: 更新既有 AppShell 测试的 mock 与断言**

打开 `frontend/src/components/layout/AppShell.test.ts`。

在 `newsStore` mock 对象（第 19-29 行）里补充 `isRefreshing` 字段：

```ts
const newsStore = {
  loadDashboardNews: vi.fn(async () => undefined),
  loadNewsRuntime: vi.fn(async () => undefined),
  loadFeedLayout: vi.fn(async () => undefined),
  refreshDashboardNews: vi.fn(async () => false),
  isRefreshing: false,
  feedQuery: {
    market: 'us',
  },
  upsertNews: vi.fn(),
  upsertNewsUpdate: vi.fn(),
};
```

在 `beforeEach`（第 109-134 行）里，`newsStore.refreshDashboardNews.mockClear();` 这一行之后补充重置：

```ts
    newsStore.refreshDashboardNews.mockClear();
    newsStore.isRefreshing = false;
```

将第 403-420 行的既有用例：

```ts
  it('does not auto-trigger full-source refresh on bootstrap and wires reconnect snapshot', async () => {
    const wrapper = mount(AppShell);
    await flushPromises();

    expect(newsStore.refreshDashboardNews).not.toHaveBeenCalled();
    expect(connectionStore.connect).toHaveBeenCalledWith(expect.any(Function), {
      onReconnect: expect.any(Function),
    });

    const options = connectionStore.connect.mock.calls[0]?.[1] as { onReconnect?: () => void };
    options.onReconnect?.();
    await flushPromises();

    expect(newsStore.loadDashboardNews).toHaveBeenCalled();
    expect(newsStore.refreshDashboardNews).not.toHaveBeenCalled();

    wrapper.unmount();
  });
```

替换为：

```ts
  it('triggers a full-source refresh once on mount, but not again on reconnect', async () => {
    const wrapper = mount(AppShell);
    await flushPromises();

    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(1);
    expect(connectionStore.connect).toHaveBeenCalledWith(expect.any(Function), {
      onReconnect: expect.any(Function),
    });

    const options = connectionStore.connect.mock.calls[0]?.[1] as { onReconnect?: () => void };
    options.onReconnect?.();
    await flushPromises();

    expect(newsStore.loadDashboardNews).toHaveBeenCalled();
    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(1);

    wrapper.unmount();
  });
```

- [ ] **Step 7: 新增周期性补抓、可见性暂停/恢复、指示器渲染的测试**

在 `frontend/src/components/layout/AppShell.test.ts` 文件末尾、最后一个 `it(...)` 块之后（`redirects root navigation...` 用例之后，`});` 收尾的 `describe` 结束括号之前）新增：

```ts
  it('polls a full-source refresh every 5 minutes while the tab stays visible', async () => {
    vi.useFakeTimers();

    const wrapper = mount(AppShell);
    await flushPromises();

    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(5 * 60_000);
    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(5 * 60_000);
    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(3);

    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(5 * 60_000);
    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(3);
    vi.useRealTimers();
  });

  it('pauses periodic refresh while hidden and refreshes immediately when visible again', async () => {
    vi.useFakeTimers();
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });

    const wrapper = mount(AppShell);
    await flushPromises();
    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(1);

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));

    await vi.advanceTimersByTimeAsync(10 * 60_000);
    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(1);

    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));

    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(5 * 60_000);
    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(3);

    wrapper.unmount();
    vi.useRealTimers();
  });

  it('shows the syncing indicator while newsStore.isRefreshing is true', () => {
    newsStore.isRefreshing = true;

    const wrapper = mount(AppShell);

    expect(wrapper.find('[data-role="news-refresh-indicator"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="news-refresh-indicator"]').text()).toContain('同步中');
  });

  it('hides the syncing indicator when newsStore.isRefreshing is false', () => {
    newsStore.isRefreshing = false;

    const wrapper = mount(AppShell);

    expect(wrapper.find('[data-role="news-refresh-indicator"]').exists()).toBe(false);
  });
```

- [ ] **Step 8: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/components/layout/AppShell.test.ts`
Expected: 全部用例 PASS（含 1 条改写用例与 4 条新增用例）。

- [ ] **Step 9: 全量跑一遍前端测试与类型检查，确认无回归**

Run: `cd frontend && npx vitest run && npm run typecheck`
Expected: 全部测试 PASS，`vue-tsc` 类型检查无报错。

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/layout/AppShell.vue frontend/src/components/layout/AppShell.test.ts
git commit -m "feat(frontend): 打开App即时触发新闻刷新+前台周期补抓+同步指示器"
```

---

## Task 4: 手动验证（本地起服务，观察真实效果）

**Files:** 无代码改动，仅验证。

- [ ] **Step 1: 启动后端**

Run: `conda run -n news-caught uvicorn app.main:app --reload --app-dir backend`
Expected: 服务正常启动，无报错。

- [ ] **Step 2: 启动前端**

Run: `cd frontend && npm run dev`
Expected: Vite dev server 启动，输出本地访问地址。

- [ ] **Step 3: 冷启动打开页面，观察 Network 面板**

打开浏览器访问前端地址，打开开发者工具 Network 面板筛选 `refresh`。

Expected: 页面加载后立刻出现一条 `POST /api/news/refresh?async_mode=true` 请求，状态码 202，响应时间在毫秒级（不阻塞页面渲染）；系统状态栏短暂出现"同步中"文案后消失（收到新条目或 15 秒超时后）。

- [ ] **Step 4: 切换标签页验证可见性暂停/恢复**

切到其他标签页停留超过 5 分钟，再切回来。

Expected: 切走期间 Network 面板无新的 refresh 请求；切回瞬间立刻出现一条新的 `POST /api/news/refresh?async_mode=true` 请求。

- [ ] **Step 5: 记录验证结果**

若手动验证中发现任何与预期不符的行为，返回对应 Task 修正代码后重新验证，不要在验证失败的情况下声明完成。

---

## Self-Review Notes（供后续读者核对，非任务步骤）

- Spec covered：触发时机与方式（Task 3 Step 3）、前台周期性补抓（Task 3 Step 1-4）、刷新状态指示（Task 2 全部 + Task 3 Step 5）、不改动后端（全计划未涉及 `backend/`）均已对应到具体任务。
- 类型一致性：`NewsRefreshAcceptedResult`（Task 1）→ `apiClient.refreshNews()` 返回类型（Task 1）→ `newsStore.refreshDashboardNews()` 消费（Task 2）→ `AppShell.vue` 调用 `newsStore.refreshDashboardNews()` / 读取 `newsStore.isRefreshing`（Task 3），命名全程一致。
- 无占位符：所有步骤均为可直接执行的完整代码块与命令。
