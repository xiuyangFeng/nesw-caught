import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getNews: vi.fn(),
  getNewsFeedLayout: vi.fn(),
  getNewsDetail: vi.fn(),
  getNewsAnalysis: vi.fn(),
  getNewsRuntime: vi.fn(),
  analyzeNews: vi.fn(),
  refreshNews: vi.fn(),
};

vi.mock('../api/client', () => ({
  apiClient,
}));

describe('newsStore', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: vi.fn(() => null),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
      },
      configurable: true,
    });
    Object.values(apiClient).forEach((fn) => fn.mockReset());
  });

  it('keeps dashboard and sentiment news lists isolated', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.getNews
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 1,
              title: 'Dashboard story',
              summary: 'Overview summary',
              source_name: 'Bloomberg',
              canonical_url: null,
              market: 'us',
              sentiment_label: 'positive',
              published_at: '2026-03-21T08:00:00Z',
              fetched_at: '2026-03-21T08:01:00Z',
            },
            {
              id: 2,
              title: 'Risk story',
              summary: 'Risk summary',
              source_name: 'Reuters',
              canonical_url: null,
              market: 'us',
              sentiment_label: 'negative',
              published_at: '2026-03-21T07:00:00Z',
              fetched_at: '2026-03-21T07:01:00Z',
            },
          ],
          next_cursor: null,
        },
        degraded: false,
      })
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 2,
              title: 'Risk story',
              summary: 'Risk summary',
              source_name: 'Reuters',
              canonical_url: null,
              market: 'us',
              sentiment_label: 'negative',
              published_at: '2026-03-21T07:00:00Z',
              fetched_at: '2026-03-21T07:01:00Z',
            },
          ],
          next_cursor: null,
        },
        degraded: false,
      });

    await (store as any).loadDashboardNews({ limit: 200 });
    await (store as any).loadSentimentNews({ sentiment_label: 'negative', limit: 300 });

    expect((store as any).dashboardItems.map((item: any) => item.id)).toEqual([1, 2]);
    expect((store as any).sentimentItems.map((item: any) => item.id)).toEqual([2]);
  });

  it('updates an existing news item and evicts it when it no longer matches the scoped query', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    (store as any).feedQuery = { sentiment_label: 'positive', limit: 10 };
    (store as any).feedItems = [
      {
        id: 9,
        title: 'Positive item',
        summary: 'Still good',
        source_name: 'Reuters',
        canonical_url: 'https://example.com/positive',
        market: 'us',
        sentiment_label: 'positive',
        published_at: '2026-03-25T02:30:00Z',
        fetched_at: '2026-03-25T02:31:00Z',
      },
    ];

    (store as any).upsertNewsUpdate({
      id: 9,
      title: 'Positive item',
      summary: 'No longer matches',
      source_name: 'Reuters',
      canonical_url: 'https://example.com/positive',
      market: 'us',
      sentiment_label: 'negative',
      published_at: '2026-03-25T02:30:00Z',
      fetched_at: '2026-03-25T02:31:00Z',
      updated_fields: ['sentiment_label'],
    });

    expect((store as any).feedItems).toEqual([]);
  });

  it('loads news runtime into store state', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.getNewsRuntime.mockResolvedValue({
      data: {
        feed_status: 'live',
        last_refresh_finished_at: '2026-03-25T02:40:00Z',
        last_news_created_at: '2026-03-25T02:39:40Z',
        last_incremental_event_at: '2026-03-25T02:39:55Z',
        degraded_market_count: 0,
        markets: [],
        sources: [
          {
            source_name: 'Example Source',
            market: 'us',
            tier: 'primary',
            status: 'ok',
            last_attempt_at: '2026-03-25T02:39:20Z',
            last_success_at: '2026-03-25T02:39:30Z',
            consecutive_failures: 0,
            avg_fetch_latency_ms: 320,
            latest_news_published_at: '2026-03-25T02:35:00Z',
            latest_news_fetched_at: '2026-03-25T02:39:30Z',
            last_error: null,
          },
        ],
      },
      degraded: false,
    });

    await (store as any).loadNewsRuntime();

    expect((store as any).newsRuntimeStatus?.feed_status).toBe('live');
    expect((store as any).sourceHealth).toHaveLength(1);
    expect((store as any).lastIncrementalAt).toBe('2026-03-25T02:39:55Z');
  });

  it('keeps feed layout stream in sync with incremental updates', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    (store as any).feedQuery = { limit: 10 };
    (store as any).feedLayout = {
      events: [],
      topics: [],
      stream: [
        {
          id: 9,
          title: 'Initial item',
          summary: 'First summary',
          source_name: 'Reuters',
          canonical_url: 'https://example.com/initial',
          market: 'us',
          sentiment_label: 'positive',
          published_at: '2026-03-25T02:30:00Z',
          fetched_at: '2026-03-25T02:31:00Z',
        },
      ],
    };
    (store as any).feedItems = [...(store as any).feedLayout.stream];

    (store as any).upsertNews({
      id: 10,
      title: 'Incremental item',
      summary: 'Fresh summary',
      source_name: 'Bloomberg',
      canonical_url: 'https://example.com/incremental',
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-03-25T02:40:00Z',
      fetched_at: '2026-03-25T02:41:00Z',
    });

    expect((store as any).feedItems[0].id).toBe(10);
    expect((store as any).feedLayout.stream[0].id).toBe(10);

    (store as any).upsertNewsUpdate({
      id: 10,
      title: 'Incremental item',
      summary: 'Updated summary',
      source_name: 'Bloomberg',
      canonical_url: 'https://example.com/incremental',
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-03-25T02:40:00Z',
      fetched_at: '2026-03-25T02:41:00Z',
      updated_fields: ['summary'],
    });

    expect((store as any).feedLayout.stream[0].summary).toBe('Updated summary');
  });

  it('keeps feed loading true until concurrent layout and stream requests both settle', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    let resolveLayout: (value: any) => void = () => {};
    let resolveNews: (value: any) => void = () => {};

    apiClient.getNewsFeedLayout.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveLayout = resolve;
        }),
    );
    apiClient.getNews.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveNews = resolve;
        }),
    );

    const layoutPromise = (store as any).loadFeedLayout({ limit_stream: 5 });
    const newsPromise = (store as any).loadFeedNews({ limit: 5 });

    expect((store as any).feedLoading).toBe(true);

    resolveLayout({
      data: { events: [], topics: [], stream: [] },
      degraded: false,
    });
    await layoutPromise;

    expect((store as any).feedLoading).toBe(true);

    resolveNews({
      data: { items: [], next_cursor: null },
      degraded: false,
    });
    await newsPromise;

    expect((store as any).feedLoading).toBe(false);
  });

  it('keeps only the latest feed layout response when requests resolve out of order', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    let resolveFirst: (value: any) => void = () => {};
    let resolveSecond: (value: any) => void = () => {};

    apiClient.getNewsFeedLayout
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecond = resolve;
          }),
      );

    const firstPromise = (store as any).loadFeedLayout({ limit_stream: 5 });
    const secondPromise = (store as any).loadFeedLayout({ limit_stream: 5 });

    resolveSecond({
      data: {
        events: [{
          event_key: 'second',
          event_title: 'Second',
          event_summary: null,
          event_type: 'general',
          market: 'us',
          sentiment_label: 'neutral',
          importance_score: 0.5,
          last_seen_at: null,
          primary_symbol: null,
          related_symbols: [],
          watchlist_hits: ['NVIDIA'],
          source_count: 1,
          news_count: 1,
          news_items: [],
        }],
        topics: [],
        stream: [],
      },
      degraded: false,
    });
    await secondPromise;

    resolveFirst({
      data: {
        events: [{
          event_key: 'first',
          event_title: 'First',
          event_summary: null,
          event_type: 'general',
          market: 'us',
          sentiment_label: 'neutral',
          importance_score: 0.4,
          last_seen_at: null,
          primary_symbol: null,
          related_symbols: [],
          watchlist_hits: ['Micron'],
          source_count: 1,
          news_count: 1,
          news_items: [],
        }],
        topics: [],
        stream: [],
      },
      degraded: false,
    });
    await firstPromise;

    expect((store as any).feedLayout.events[0].event_key).toBe('second');
    expect((store as any).feedLayout.events[0].watchlist_hits).toEqual(['NVIDIA']);
  });

  it('keeps only the latest raw feed response when requests resolve out of order', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    let resolveFirst: (value: any) => void = () => {};
    let resolveSecond: (value: any) => void = () => {};

    apiClient.getNews
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecond = resolve;
          }),
      );

    const firstPromise = (store as any).loadFeedNews({ limit: 5, q: 'first' });
    const secondPromise = (store as any).loadFeedNews({ limit: 5, q: 'second' });

    resolveSecond({
      data: {
        items: [
          {
            id: 2,
            title: 'Second response',
            summary: 'second',
            source_name: 'Reuters',
            canonical_url: 'https://example.com/second',
            market: 'us',
            sentiment_label: 'neutral',
            published_at: '2026-03-25T02:40:00Z',
            fetched_at: '2026-03-25T02:41:00Z',
          },
        ],
        next_cursor: null,
      },
      degraded: false,
    });
    await secondPromise;

    resolveFirst({
      data: {
        items: [
          {
            id: 1,
            title: 'First response',
            summary: 'first',
            source_name: 'Bloomberg',
            canonical_url: 'https://example.com/first',
            market: 'us',
            sentiment_label: 'neutral',
            published_at: '2026-03-25T02:30:00Z',
            fetched_at: '2026-03-25T02:31:00Z',
          },
        ],
        next_cursor: null,
      },
      degraded: false,
    });
    await firstPromise;

    expect((store as any).feedItems[0].id).toBe(2);
  });

  it('appends older feed items when loadMoreFeedNews is called', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.getNews
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 2,
              title: 'Latest',
              summary: 'latest',
              source_name: 'Reuters',
              canonical_url: 'https://example.com/latest',
              market: 'us',
              sentiment_label: 'neutral',
              published_at: '2026-03-25T02:40:00Z',
              fetched_at: '2026-03-25T02:41:00Z',
            },
          ],
          next_cursor: 'cursor-2',
        },
        degraded: false,
      })
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 1,
              title: 'Older',
              summary: 'older',
              source_name: 'Bloomberg',
              canonical_url: 'https://example.com/older',
              market: 'us',
              sentiment_label: 'neutral',
              published_at: '2026-03-25T02:30:00Z',
              fetched_at: '2026-03-25T02:31:00Z',
            },
          ],
          next_cursor: null,
        },
        degraded: false,
      });

    await (store as any).loadFeedNews({ limit: 1 });
    await (store as any).loadMoreFeedNews();

    expect((store as any).feedItems.map((item: any) => item.id)).toEqual([2, 1]);
    expect((store as any).feedNextCursor).toBeNull();
  });

  it('does not truncate paginated feed items back to the base limit on SSE upserts', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    const makeItem = (id: number) => ({
      id,
      title: `Item ${id}`,
      summary: `summary ${id}`,
      source_name: 'Reuters',
      canonical_url: `https://example.com/${id}`,
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-03-25T02:30:00Z',
      fetched_at: '2026-03-25T02:31:00Z',
    });

    apiClient.getNews
      .mockResolvedValueOnce({
        data: { items: [makeItem(3)], next_cursor: 'cursor-1' },
        degraded: false,
      })
      .mockResolvedValueOnce({
        data: { items: [makeItem(2), makeItem(1)], next_cursor: null },
        degraded: false,
      });

    await (store as any).loadFeedNews({ limit: 1 });
    await (store as any).loadMoreFeedNews();
    expect((store as any).feedItems.map((item: any) => item.id)).toEqual([3, 2, 1]);

    (store as any).upsertNews(makeItem(4));

    // The list keeps its expanded length instead of collapsing to limit=1.
    expect((store as any).feedItems.map((item: any) => item.id)).toEqual([4, 3, 2]);
  });

  it('caps the layout stream with the layout stream limit, not the feed query limit', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    const makeItem = (id: number) => ({
      id,
      title: `Item ${id}`,
      summary: `summary ${id}`,
      source_name: 'Reuters',
      canonical_url: `https://example.com/${id}`,
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-03-25T02:30:00Z',
      fetched_at: '2026-03-25T02:31:00Z',
    });

    apiClient.getNewsFeedLayout.mockResolvedValue({
      data: { events: [], topics: [], stream: [makeItem(2), makeItem(1)] },
      degraded: false,
    });

    await (store as any).loadFeedLayout({ limit_stream: 3 });
    (store as any).feedQuery = { limit: 1 };

    (store as any).upsertNews(makeItem(3));
    expect((store as any).feedLayout.stream.map((item: any) => item.id)).toEqual([3, 2, 1]);

    (store as any).upsertNews(makeItem(4));
    expect((store as any).feedLayout.stream.map((item: any) => item.id)).toEqual([4, 3, 2]);
  });

  it('resets scoped loading state when a load fails', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.getNews.mockRejectedValue(new Error('backend offline'));

    await expect((store as any).loadDashboardNews({ limit: 5 })).rejects.toThrow('backend offline');
    expect((store as any).dashboardLoading).toBe(false);

    await expect((store as any).loadSentimentNews({ limit: 5 })).rejects.toThrow('backend offline');
    expect((store as any).sentimentLoading).toBe(false);
  });

  it('keeps only the latest dashboard response when requests resolve out of order', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    const makeItem = (id: number, title: string) => ({
      id,
      title,
      summary: title,
      source_name: 'Reuters',
      canonical_url: `https://example.com/${id}`,
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-03-25T02:30:00Z',
      fetched_at: '2026-03-25T02:31:00Z',
    });

    const createDeferred = () => {
      let resolve!: (value: any) => void;
      const promise = new Promise((res) => {
        resolve = res;
      });
      return { promise, resolve };
    };

    const first = createDeferred();
    const second = createDeferred();

    apiClient.getNews
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);

    const firstPromise = (store as any).loadDashboardNews({ limit: 5, q: 'first' });
    const secondPromise = (store as any).loadDashboardNews({ limit: 5, q: 'second' });

    second.resolve({
      data: { items: [makeItem(2, 'Second response')], next_cursor: null },
      degraded: false,
    });
    await secondPromise;

    first.resolve({
      data: { items: [makeItem(1, 'First response')], next_cursor: null },
      degraded: false,
    });
    await firstPromise;

    expect((store as any).dashboardItems.map((item: any) => item.id)).toEqual([2]);
    expect((store as any).dashboardLoading).toBe(false);
  });

  it('returns false from refreshDashboardNews when the refresh request fails', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    apiClient.refreshNews.mockRejectedValue(new Error('backend offline'));

    await expect((store as any).refreshDashboardNews()).resolves.toBe(false);
  });

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
});
