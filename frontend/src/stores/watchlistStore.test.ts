import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getWatchlist: vi.fn(),
  getWatchlistQuotes: vi.fn(),
  refreshMarketQuotes: vi.fn(),
  getStockQuoteDetail: vi.fn(),
  getRelatedNews: vi.fn(),
  createWatchlist: vi.fn(),
  getWatchlistCandidates: vi.fn(),
  deleteWatchlist: vi.fn(),
};

vi.mock('../api/client', () => ({
  apiClient,
}));

const runtimeStatusStore = {
  loadRuntimeStatus: vi.fn(async () => undefined),
};

vi.mock('./runtimeStatusStore', () => ({
  useRuntimeStatusStore: () => runtimeStatusStore,
}));

describe('watchlistStore', () => {
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

  it('loads watchlist candidates into store state', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();

    apiClient.getWatchlistCandidates.mockResolvedValue({
      data: [
        { symbol: '0700.HK', market: 'hk', display_name: 'Tencent', aliases: ['腾讯'] },
        { symbol: 'AAPL', market: 'us', display_name: 'Apple', aliases: ['苹果'] },
      ],
      degraded: false,
    });

    await (store as any).loadCandidates();

    expect((store as any).candidates).toHaveLength(2);
    expect((store as any).candidates[0].symbol).toBe('0700.HK');
  });

  it('deletes the selected symbol and falls back to the next item', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();

    const initialItems = [
      { id: 1, symbol: '0700.HK', market: 'hk', display_name: 'Tencent', is_active: true, alert_threshold: 3, alert_mode: 'fixed' },
      { id: 2, symbol: 'AAPL', market: 'us', display_name: 'Apple', is_active: true, alert_threshold: 2, alert_mode: 'fixed' },
    ];
    const remainingItems = [initialItems[1]];
    const initialQuotes = [
      {
        symbol: '0700.HK',
        market: 'hk',
        display_name: 'Tencent',
        provider_symbol: '0700.HK',
        price: 550.5,
        change_amount: 0.5,
        change_percent: 0.09,
        open_price: 546.5,
        previous_close: 550,
        day_high: 552,
        day_low: 542.5,
        volume: 21366376,
        status: 'ok',
        source: 'yahoo_finance',
        message: null,
        is_abnormal: false,
        abnormal_reason: null,
        fetched_at: '2026-03-18T11:25:00Z',
      },
      {
        symbol: 'AAPL',
        market: 'us',
        display_name: 'Apple',
        provider_symbol: 'AAPL',
        price: 254.23,
        change_amount: 0.08,
        change_percent: 0.03,
        open_price: 253.08,
        previous_close: 254.15,
        day_high: 255.13,
        day_low: 252.18,
        volume: 27556024,
        status: 'ok',
        source: 'yahoo_finance',
        message: null,
        is_abnormal: false,
        abnormal_reason: null,
        fetched_at: '2026-03-18T11:25:00Z',
      },
    ];
    const remainingQuotes = [initialQuotes[1]];
    apiClient.getWatchlist
      .mockResolvedValueOnce({ data: initialItems, degraded: false })
      .mockResolvedValueOnce({ data: remainingItems, degraded: false });
    apiClient.getWatchlistQuotes
      .mockResolvedValueOnce({ data: initialQuotes, degraded: false })
      .mockResolvedValueOnce({ data: remainingQuotes, degraded: false });
    apiClient.deleteWatchlist.mockResolvedValue(undefined);

    await store.loadWatchlist();
    store.selectedSymbol = '0700.HK';
    (store as any).relatedNews = { '0700.HK': [{ id: 1 }], AAPL: [{ id: 2 }] };

    await (store as any).deleteWatchlist('0700.HK');

    expect(apiClient.deleteWatchlist).toHaveBeenCalledWith('0700.HK');
    expect(store.items.map((item) => item.symbol)).toEqual(['AAPL']);
    expect(store.selectedSymbol).toBe('AAPL');
    expect((store as any).relatedNews['0700.HK']).toBeUndefined();
  });

  it('loads watchlist data without requesting runtime status', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();

    apiClient.getWatchlist.mockResolvedValue({ data: [], degraded: false });
    apiClient.getWatchlistQuotes.mockResolvedValue({ data: [], degraded: false });

    await store.loadWatchlist();

    expect(apiClient.getWatchlist).toHaveBeenCalledTimes(1);
    expect(apiClient.getWatchlistQuotes).toHaveBeenCalledTimes(1);
  });

  it('runs manual market refresh and reloads watchlist state', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();

    apiClient.refreshMarketQuotes.mockResolvedValue({
      data: {
        quotes_count: 1,
        symbols: ['0700.HK'],
        triggered_at: '2026-03-23T06:00:00Z',
      },
      degraded: false,
    });
    apiClient.getWatchlist.mockResolvedValue({ data: [], degraded: false });
    apiClient.getWatchlistQuotes.mockResolvedValue({ data: [], degraded: false });
    await (store as any).refreshMarketQuotes();

    expect(apiClient.refreshMarketQuotes).toHaveBeenCalledTimes(1);
    expect(apiClient.getWatchlist).toHaveBeenCalledTimes(1);
    expect(apiClient.getWatchlistQuotes).toHaveBeenCalledTimes(1);
    expect(runtimeStatusStore.loadRuntimeStatus).toHaveBeenCalledTimes(1);
    expect((store as any).lastManualRefreshResult?.quotes_count).toBe(1);
    expect((store as any).lastManualRefreshResult?.symbols).toEqual(['0700.HK']);
  });
});
