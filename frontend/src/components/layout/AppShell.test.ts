import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AppShell from './AppShell.vue';

const routeState = {
  path: '/news',
};

const connectionStore = {
  state: 'live',
  lastEventAt: '2026-03-18T01:00:00Z',
  loadStreamStatus: vi.fn(async () => undefined),
  applyStreamStatus: vi.fn(),
  connect: vi.fn(),
  disconnect: vi.fn(),
};

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

const marketStore = {
  loadSnapshots: vi.fn(async () => undefined),
  upsertSnapshot: vi.fn(),
};

const topicStore = {
  loadTopics: vi.fn(async () => undefined),
  upsertTopic: vi.fn(),
};

const watchlistStore = {
  loadWatchlist: vi.fn(async () => undefined),
};

const runtimeStatusStore = {
  loadRuntimeStatus: vi.fn(async (): Promise<void> => undefined),
  loadRuntimeStatusIfStale: vi.fn(async (): Promise<void> => undefined),
  usingMock: false,
  streamStatus: {
    mode: 'sse',
    status: 'ok',
    backend: 'hybrid',
    redis_enabled: true,
    last_published_at: null,
    last_event_name: null,
    last_error: null,
    market_worker: null,
  },
  marketWorkerStatus: {
    name: 'market_quote_producer',
    status: 'degraded',
    last_heartbeat_at: '2026-03-23T05:00:00Z',
    last_success_at: '2026-03-23T04:58:00Z',
    last_failure_at: '2026-03-23T04:59:00Z',
    last_error: 'provider timeout',
    cycle_count: 12,
    success_count: 11,
    failure_count: 1,
    last_quotes_count: 2,
  },
};

vi.mock('vue-router', () => ({
  RouterLink: {
    props: ['to'],
    template: '<a :href="typeof to === \'string\' ? to : to.path"><slot /></a>',
  },
  RouterView: {
    template: '<div data-role="router-view-stub">router view</div>',
  },
  useRoute: () => routeState,
}));

vi.mock('../../stores/connectionStore', () => ({
  useConnectionStore: () => connectionStore,
}));

vi.mock('../../stores/newsStore', () => ({
  useNewsStore: () => newsStore,
}));

vi.mock('../../stores/marketStore', () => ({
  useMarketStore: () => marketStore,
}));

vi.mock('../../stores/topicStore', () => ({
  useTopicStore: () => topicStore,
}));

vi.mock('../../stores/watchlistStore', () => ({
  useWatchlistStore: () => watchlistStore,
}));

vi.mock('../../stores/runtimeStatusStore', () => ({
  useRuntimeStatusStore: () => runtimeStatusStore,
}));

describe('AppShell', () => {
  // 本任务在 bootstrap() 中新增了 document 级别的 visibilitychange 监听。之前的部分用例
  // 只 mount 未 unmount(依赖 wrapper 被 GC),这些"泄漏"的实例此前无副作用,但现在会在
  // document 上累积监听器并对后续用例的 dispatchEvent 重复响应,导致断言次数被放大。
  // enableAutoUnmount 让每个用例结束时自动 unmount 所有 wrapper,从根上消除跨用例污染,
  // 且不需要逐个改写既有用例。
  enableAutoUnmount(afterEach);

  beforeEach(() => {
    vi.useRealTimers();
    routeState.path = '/news';
    connectionStore.state = 'live';
    connectionStore.lastEventAt = '2026-03-18T01:00:00Z';
    connectionStore.loadStreamStatus.mockClear();
    connectionStore.applyStreamStatus.mockClear();
    connectionStore.connect.mockClear();
    connectionStore.disconnect.mockClear();
    newsStore.loadDashboardNews.mockClear();
    newsStore.loadNewsRuntime.mockClear();
    newsStore.loadFeedLayout.mockClear();
    newsStore.refreshDashboardNews.mockClear();
    newsStore.isRefreshing = false;
    newsStore.feedQuery = {
      market: 'us',
    };
    newsStore.upsertNews.mockClear();
    newsStore.upsertNewsUpdate.mockClear();
    marketStore.loadSnapshots.mockClear();
    marketStore.upsertSnapshot.mockClear();
    topicStore.loadTopics.mockClear();
    topicStore.upsertTopic.mockClear();
    watchlistStore.loadWatchlist.mockClear();
    runtimeStatusStore.loadRuntimeStatus.mockClear();
    runtimeStatusStore.loadRuntimeStatusIfStale.mockClear();
  });

  it('renders terminal shell landmarks for brand, nav, and system status', () => {
    const wrapper = mount(AppShell);

    expect(wrapper.find('[data-role="system-header"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="system-desk-chip"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="system-desk-note"]').text()).toContain('Discovery / Events / Evidence');
    expect(wrapper.text()).not.toContain('跟踪新闻、主题热度、自选股异动与流式连接状态。');
    expect(wrapper.find('[data-role="primary-nav"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="system-status"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="shell-status-rail"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="shell-status-rail"]').text()).toContain('SSE LIVE');
    expect(wrapper.find('[data-role="shell-status-rail"]').text()).toContain('Workspace latest-event discovery');
    expect(wrapper.find('[data-role="system-status"]').text()).toContain('Last event');
    expect(wrapper.find('[data-role="system-status"]').text()).toContain('market_quote_producer');
    expect(wrapper.find('[data-role="system-status"]').text()).toContain('provider timeout');
    expect(wrapper.find('[data-role="runtime-diagnostic-headline"]').text()).toContain('market worker');
    expect(wrapper.find('[data-role="runtime-diagnostic-action"]').text()).toContain('打开 Watchlist');
    expect(wrapper.find('[data-role="system-status"]').text()).toContain('Workspace latest-event discovery');
    expect(wrapper.find('[data-role="router-view-stub"]').exists()).toBe(true);
  });

  it('uses the shared stacked layout for shell status indicator units', () => {
    const wrapper = mount(AppShell);

    expect(wrapper.find('[data-role="system-status-unit"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="market-worker-status-unit"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="system-status-unit"]').classes()).toContain('grid');
    expect(wrapper.find('[data-role="market-worker-status-unit"]').classes()).toContain('grid');
    expect(wrapper.find('[data-role="system-status-unit"]').classes()).toContain('grid-cols-1');
    expect(wrapper.find('[data-role="market-worker-status-unit"]').classes()).toContain('grid-cols-1');
    expect(wrapper.find('[data-role="market-worker-pill"]').classes()).toContain('w-full');
    expect(wrapper.find('[data-role="market-worker-shell-status"]').text()).toContain('Market worker');
    expect(wrapper.find('[data-role="market-worker-shell-status"]').text()).toContain('market_quote_producer');
  });

  it('marks the active route with a dedicated terminal signal', () => {
    routeState.path = '/news/42';

    const wrapper = mount(AppShell);

    const activeLink = wrapper.find('[data-route-active="true"]');
    expect(activeLink.exists()).toBe(true);
    expect(activeLink.text()).toContain('最新事件');
    expect(activeLink.text()).toContain('Events');
    expect(activeLink.find('[data-role="nav-active-signal"]').exists()).toBe(true);
  });

  it('updates the shell rail signal tone when connection state is degraded', () => {
    connectionStore.state = 'degraded';

    const wrapper = mount(AppShell);

    expect(wrapper.find('[data-role="shell-status-rail"]').text()).toContain('SSE DEGRADED');
    expect(wrapper.find('[data-role="shell-status-rail-signal"]').classes()).toContain('bg-warning');
  });

  it('refreshes runtime status after watchlist movement and keepalive events', async () => {
    mount(AppShell);
    await flushPromises();

    const handleEvent = connectionStore.connect.mock.calls[0]?.[0];
    expect(handleEvent).toBeTypeOf('function');

    handleEvent({
      type: 'watchlist.movement',
      occurred_at: '2026-03-23T08:00:00Z',
      payload: {
        symbol: '0700.HK',
        market: 'hk',
        display_name: 'Tencent',
        provider_symbol: '0700.HK',
        price: 550,
        change_amount: 1,
        change_percent: 0.2,
        open_price: 548,
        previous_close: 549,
        day_high: 551,
        day_low: 545,
        volume: 123456,
        status: 'ok',
        source: 'yahoo_finance',
        message: null,
        is_abnormal: false,
        abnormal_reason: null,
        fetched_at: '2026-03-23T08:00:00Z',
      },
    });
    handleEvent({
      type: 'stream.keepalive',
      occurred_at: '2026-03-23T08:00:05Z',
      payload: { status: 'ok' },
    });

    expect(runtimeStatusStore.loadRuntimeStatusIfStale).toHaveBeenCalledTimes(2);
  });

  it('routes news.updated events into the news store', async () => {
    mount(AppShell);
    await flushPromises();

    const handleEvent = connectionStore.connect.mock.calls[0]?.[0];
    expect(handleEvent).toBeTypeOf('function');

    const updatedItem = {
      id: 7,
      title: 'Updated headline',
      summary: 'Updated summary',
      source_name: 'Reuters',
      canonical_url: 'https://example.com/updated',
      market: 'us',
      sentiment_label: 'positive',
      published_at: '2026-03-25T02:30:00Z',
      fetched_at: '2026-03-25T02:31:00Z',
      updated_fields: ['sentiment_label'],
    };

    handleEvent({
      type: 'news.updated',
      occurred_at: '2026-03-25T02:31:00Z',
      payload: updatedItem,
    });

    expect(newsStore.upsertNewsUpdate).toHaveBeenCalledWith(updatedItem);
  });

  it('starts low-frequency runtime polling after bootstrap and clears it on unmount', async () => {
    vi.useFakeTimers();

    const wrapper = mount(AppShell);
    await flushPromises();

    expect(runtimeStatusStore.loadRuntimeStatusIfStale).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(60_000);

    expect(runtimeStatusStore.loadRuntimeStatusIfStale).toHaveBeenCalledTimes(1);
    expect(runtimeStatusStore.loadRuntimeStatusIfStale).toHaveBeenCalledWith(45);

    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(60_000);

    expect(runtimeStatusStore.loadRuntimeStatusIfStale).toHaveBeenCalledTimes(1);
  });

  it('does not start runtime polling after unmount if bootstrap resolves late', async () => {
    vi.useFakeTimers();

    let resolveRuntimeStatusLoad: () => void = () => {};
    runtimeStatusStore.loadRuntimeStatus.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          resolveRuntimeStatusLoad = resolve;
        }),
    );

    const wrapper = mount(AppShell);
    wrapper.unmount();

    resolveRuntimeStatusLoad();
    await flushPromises();
    await vi.advanceTimersByTimeAsync(60_000);

    expect(runtimeStatusStore.loadRuntimeStatusIfStale).not.toHaveBeenCalled();
  });

  it('loads shell stores on mount and disconnects on unmount', async () => {
    const wrapper = mount(AppShell);
    await flushPromises();

    expect(connectionStore.loadStreamStatus).not.toHaveBeenCalled();
    expect(connectionStore.applyStreamStatus).toHaveBeenCalledWith(runtimeStatusStore.streamStatus, false);
    expect(newsStore.loadDashboardNews).toHaveBeenCalledWith({ limit: 200 });
    expect(marketStore.loadSnapshots).toHaveBeenCalledTimes(1);
    expect(topicStore.loadTopics).toHaveBeenCalledTimes(1);
    expect(watchlistStore.loadWatchlist).toHaveBeenCalledTimes(1);
    expect(runtimeStatusStore.loadRuntimeStatus).toHaveBeenCalledTimes(1);

    wrapper.unmount();

    expect(connectionStore.disconnect).toHaveBeenCalledTimes(1);
  });

  it('keeps news.created on the local incremental path without a layout refetch', async () => {
    vi.useFakeTimers();

    const wrapper = mount(AppShell);
    await flushPromises();

    const handleEvent = connectionStore.connect.mock.calls[0]?.[0];
    expect(handleEvent).toBeTypeOf('function');

    const createdItem = {
      id: 8,
      title: 'Fresh headline',
      summary: 'Fresh summary',
      source_name: 'Reuters',
      canonical_url: 'https://example.com/fresh',
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-03-25T02:30:00Z',
      fetched_at: '2026-03-25T02:31:00Z',
    };

    newsStore.loadFeedLayout.mockClear();
    handleEvent({
      type: 'news.created',
      occurred_at: '2026-03-25T02:31:00Z',
      payload: createdItem,
    });

    expect(newsStore.upsertNews).toHaveBeenCalledWith(createdItem);

    await vi.advanceTimersByTimeAsync(1_000);

    expect(newsStore.loadFeedLayout).not.toHaveBeenCalled();

    wrapper.unmount();
    vi.useRealTimers();
  });

  it('refreshes the layout on topic.updated and on the 60s poll, safely when feedQuery is missing', async () => {
    vi.useFakeTimers();
    (newsStore as { feedQuery?: { market?: string } | undefined }).feedQuery = undefined;

    const wrapper = mount(AppShell);
    await flushPromises();

    const handleEvent = connectionStore.connect.mock.calls[0]?.[0];
    expect(handleEvent).toBeTypeOf('function');

    newsStore.loadFeedLayout.mockClear();

    expect(() =>
      handleEvent({
        type: 'topic.updated',
        occurred_at: '2026-03-25T02:31:00Z',
        payload: {
          id: 3,
          topic_title: 'AI Infra',
          importance_score: 0.9,
          news_count: 4,
          last_seen_at: '2026-03-25T02:30:00Z',
        },
      }),
    ).not.toThrow();

    await vi.advanceTimersByTimeAsync(500);

    expect(newsStore.loadFeedLayout).toHaveBeenCalledTimes(1);
    expect(newsStore.loadFeedLayout).toHaveBeenLastCalledWith({
      market: undefined,
      limit_events: 6,
      limit_topics: 6,
      limit_stream: 100,
    });

    await vi.advanceTimersByTimeAsync(60_000);

    expect(newsStore.loadFeedLayout).toHaveBeenCalledTimes(2);

    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(60_000);

    expect(newsStore.loadFeedLayout).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

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

  it('does not start periodic polling when the tab is hidden at mount, but resumes once visible', async () => {
    vi.useFakeTimers();
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });

    const wrapper = mount(AppShell);
    await flushPromises();
    // 挂载时的一次性 triggerNewsRefresh() 与 visibilityState 无关,始终会触发。
    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(10 * 60_000);
    // 挂载时页面已隐藏,前台周期轮询不应启动,即便过去了 5 分钟以上。
    expect(newsStore.refreshDashboardNews).toHaveBeenCalledTimes(1);

    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));

    // 变为可见后立即刷新一次,并恢复周期轮询。
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

  it('redirects root navigation to the news discovery page', async () => {
    vi.resetModules();
    vi.doUnmock('vue-router');

    const { default: router } = await import('../../router');

    await router.push('/');

    expect(router.currentRoute.value.path).toBe('/news');
    expect(router.currentRoute.value.name).toBe('news-feed');
  });
});
