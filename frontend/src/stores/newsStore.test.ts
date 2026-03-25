import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getNews: vi.fn(),
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
});
