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
        data: [
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
        degraded: false,
      })
      .mockResolvedValueOnce({
        data: [
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

    let resolveLayout: ((value: any) => void) | null = null;
    let resolveNews: ((value: any) => void) | null = null;

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

    resolveLayout?.({
      data: { events: [], topics: [], stream: [] },
      degraded: false,
    });
    await layoutPromise;

    expect((store as any).feedLoading).toBe(true);

    resolveNews?.({
      data: [],
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

    let resolveFirst: ((value: any) => void) | null = null;
    let resolveSecond: ((value: any) => void) | null = null;

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

    resolveSecond?.({
      data: {
        events: [{ event_key: 'second', event_title: 'Second', event_summary: null, event_type: 'general', market: 'us', sentiment_label: 'neutral', importance_score: 0.5, last_seen_at: null, primary_symbol: null, related_symbols: [], source_count: 1, news_count: 1, news_items: [] }],
        topics: [],
        stream: [],
      },
      degraded: false,
    });
    await secondPromise;

    resolveFirst?.({
      data: {
        events: [{ event_key: 'first', event_title: 'First', event_summary: null, event_type: 'general', market: 'us', sentiment_label: 'neutral', importance_score: 0.4, last_seen_at: null, primary_symbol: null, related_symbols: [], source_count: 1, news_count: 1, news_items: [] }],
        topics: [],
        stream: [],
      },
      degraded: false,
    });
    await firstPromise;

    expect((store as any).feedLayout.events[0].event_key).toBe('second');
  });

  it('keeps only the latest raw feed response when requests resolve out of order', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useNewsStore } = await import('./newsStore');
    setActivePinia(createPinia());
    const store = useNewsStore();

    let resolveFirst: ((value: any) => void) | null = null;
    let resolveSecond: ((value: any) => void) | null = null;

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

    resolveSecond?.({
      data: [
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
      degraded: false,
    });
    await secondPromise;

    resolveFirst?.({
      data: [
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
      degraded: false,
    });
    await firstPromise;

    expect((store as any).feedItems[0].id).toBe(2);
  });
});
