import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getNews: vi.fn(),
  getNewsDetail: vi.fn(),
  getNewsAnalysis: vi.fn(),
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
});
