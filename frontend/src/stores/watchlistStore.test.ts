import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getWatchlist: vi.fn(),
  getWatchlistQuotes: vi.fn(),
  getWatchlistSparklines: vi.fn(),
  refreshMarketQuotes: vi.fn(),
  getStockQuoteDetail: vi.fn(),
  getStockKline: vi.fn(),
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

  it('clears detail state after deleting the last remaining symbol', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();

    apiClient.getWatchlist
      .mockResolvedValueOnce({
        data: [{ id: 1, symbol: '0700.HK', market: 'hk', display_name: 'Tencent', is_active: true, alert_threshold: 3, alert_mode: 'fixed' }],
        degraded: false,
      })
      .mockResolvedValueOnce({ data: [], degraded: false });
    apiClient.getWatchlistQuotes
      .mockResolvedValueOnce({
        data: [{
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
        }],
        degraded: false,
      })
      .mockResolvedValueOnce({ data: [], degraded: false });
    apiClient.deleteWatchlist.mockResolvedValue(undefined);

    await store.loadWatchlist();
    store.selectedSymbol = '0700.HK';
    (store as any).klineData = {
      symbol: '0700.HK',
      interval: '1d',
      range: '6mo',
      stale: false,
      candles: [],
      indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
      news_events: [],
    };
    (store as any).detailNews = [{ id: 1, title: 'old news' }];

    await (store as any).deleteWatchlist('0700.HK');

    expect(store.selectedSymbol).toBeNull();
    expect((store as any).klineData).toBeNull();
    expect((store as any).detailNews).toEqual([]);
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

  it('loads sparklines together with watchlist quotes', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();

    apiClient.getWatchlist.mockResolvedValue({
      data: [{ id: 1, symbol: '0700.HK', market: 'hk', display_name: 'Tencent', is_active: true, alert_threshold: 3, alert_mode: 'fixed' }],
      degraded: false,
    });
    apiClient.getWatchlistQuotes.mockResolvedValue({
      data: [
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
      ],
      degraded: false,
    });
    apiClient.getWatchlistSparklines.mockResolvedValue({
      data: {
        '0700.HK': { prices: [540, 545, 550.5] },
      },
      degraded: false,
    });

    await store.loadWatchlist();

    expect(apiClient.getWatchlistSparklines).toHaveBeenCalledWith(['0700.HK']);
    expect((store as any).sparklines['0700.HK']).toEqual([540, 545, 550.5]);
  });

  it('selects a symbol and loads kline plus related news concurrently', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();

    apiClient.getStockKline.mockResolvedValue({
      data: {
        symbol: '0700.HK',
        interval: '1d',
        range: '6mo',
        stale: false,
        candles: [{ time: '2026-03-20', open: 500, high: 505, low: 498, close: 503, volume: 10 }],
        indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
        news_events: [],
      },
      degraded: false,
    });
    apiClient.getRelatedNews.mockResolvedValue({
      data: [{ id: 1, title: 'Tencent update', summary: '...', source_name: 'Reuters', canonical_url: null, market: 'hk', sentiment_label: 'positive', published_at: null, fetched_at: '2026-03-20T00:00:00Z' }],
      degraded: false,
    });

    await (store as any).selectSymbol('0700.HK');

    expect(apiClient.getStockKline).toHaveBeenCalledWith('0700.HK', '1d', '6mo');
    expect(apiClient.getRelatedNews).toHaveBeenCalledWith('0700.HK');
    expect(store.selectedSymbol).toBe('0700.HK');
    expect((store as any).klineData?.symbol).toBe('0700.HK');
    expect((store as any).detailNews).toHaveLength(1);
  });

  it('switches dashboard period using the fixed spec mapping', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();
    store.selectedSymbol = '0700.HK';
    apiClient.getStockKline.mockResolvedValue({
      data: {
        symbol: '0700.HK',
        interval: '1wk',
        range: '1y',
        stale: false,
        candles: [],
        indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
        news_events: [],
      },
      degraded: false,
    });

    await (store as any).switchPeriod('1W');

    expect(apiClient.getStockKline).toHaveBeenCalledWith('0700.HK', '1wk', '1y');
    expect((store as any).currentPeriod).toBe('1W');
  });

  it('ignores stale kline responses when periods are switched quickly', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();
    store.selectedSymbol = '0700.HK';

    let resolveFirst!: (value: any) => void;
    let resolveSecond!: (value: any) => void;
    apiClient.getStockKline
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve; }));

    const first = (store as any).switchPeriod('1W');
    const second = (store as any).switchPeriod('1M');

    resolveSecond({
      data: {
        symbol: '0700.HK',
        interval: '1mo',
        range: '2y',
        stale: false,
        candles: [{ time: '2026-03-20', open: 1, high: 2, low: 1, close: 2, volume: 10 }],
        indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
        news_events: [],
      },
      degraded: false,
    });
    resolveFirst({
      data: {
        symbol: '0700.HK',
        interval: '1wk',
        range: '1y',
        stale: false,
        candles: [{ time: '2026-03-19', open: 1, high: 3, low: 1, close: 3, volume: 10 }],
        indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
        news_events: [],
      },
      degraded: false,
    });

    await Promise.all([first, second]);

    expect((store as any).currentPeriod).toBe('1M');
    expect((store as any).klineData?.interval).toBe('1mo');
  });

  it('keeps the list usable when kline loading fails', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();
    store.items = [{ id: 1, symbol: '0700.HK', market: 'hk', display_name: 'Tencent', is_active: true, alert_threshold: 3, alert_mode: 'fixed' }];
    apiClient.getStockKline.mockRejectedValue(new Error('timeout'));
    apiClient.getRelatedNews.mockResolvedValue({ data: [], degraded: false });

    await (store as any).selectSymbol('0700.HK');

    expect((store as any).klineError).toContain('K 线');
    expect(store.items).toHaveLength(1);
    expect((store as any).detailNews).toEqual([]);
  });

  it('clears detail loading when quote detail loading fails', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();
    apiClient.getStockQuoteDetail.mockRejectedValue(new Error('timeout'));

    await expect((store as any).loadQuoteDetail('AAPL')).rejects.toThrow('timeout');

    expect(store.detailLoading).toBe(false);
    expect(store.quoteDetail).toBeNull();
  });

  it('ignores stale detail responses after the user switches symbols quickly', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useWatchlistStore } = await import('./watchlistStore');
    setActivePinia(createPinia());
    const store = useWatchlistStore();

    let resolveFirstKline!: (value: any) => void;
    let resolveSecondKline!: (value: any) => void;
    apiClient.getStockKline
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirstKline = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecondKline = resolve;
          }),
      );
    apiClient.getRelatedNews.mockResolvedValue({ data: [], degraded: false });

    const firstSelection = (store as any).selectSymbol('0700.HK');
    const secondSelection = (store as any).selectSymbol('AAPL');

    resolveSecondKline({
      data: {
        symbol: 'AAPL',
        interval: '1d',
        range: '6mo',
        stale: false,
        candles: [],
        indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
        news_events: [],
      },
      degraded: false,
    });
    resolveFirstKline({
      data: {
        symbol: '0700.HK',
        interval: '1d',
        range: '6mo',
        stale: false,
        candles: [],
        indicators: { ma5: [], ma10: [], ma20: [], ma60: [], macd: [], kdj: [], bollinger: [] },
        news_events: [],
      },
      degraded: false,
    });

    await Promise.all([firstSelection, secondSelection]);

    expect(store.selectedSymbol).toBe('AAPL');
    expect((store as any).klineData?.symbol).toBe('AAPL');
  });
});
