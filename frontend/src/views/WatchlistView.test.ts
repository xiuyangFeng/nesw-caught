import { mount, flushPromises } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

Object.defineProperty(globalThis, 'localStorage', {
  value: {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  },
  configurable: true,
});

import WatchlistView from './WatchlistView.vue';
const push = vi.fn();

const watchlistStore = reactive({
  candidates: [
    { symbol: '0700.HK', market: 'hk', display_name: 'Tencent', aliases: ['腾讯'] },
    { symbol: 'BABA', market: 'us', display_name: 'Alibaba', aliases: ['阿里'] },
  ],
  items: [
    { id: 1, symbol: '0700.HK', market: 'hk', display_name: 'Tencent', is_active: true, alert_threshold: 3, alert_mode: 'fixed' },
    { id: 2, symbol: 'AAPL', market: 'us', display_name: 'Apple', is_active: true, alert_threshold: 2, alert_mode: 'fixed' },
  ],
  quotes: [
    {
      symbol: '0700.HK',
      market: 'hk',
      display_name: 'Tencent',
      provider_symbol: '0700.HK',
      price: 550.5,
      change_amount: 5.5,
      change_percent: 1.01,
      open_price: 546.5,
      previous_close: 545,
      day_high: 552,
      day_low: 542.5,
      volume: 21366376,
      status: 'ok',
      source: 'yahoo_finance',
      message: null,
      is_abnormal: true,
      abnormal_reason: 'price_move',
      fetched_at: '2026-03-18T11:25:00Z',
    },
    {
      symbol: 'AAPL',
      market: 'us',
      display_name: 'Apple',
      provider_symbol: 'AAPL',
      price: 200.1,
      change_amount: -1.2,
      change_percent: -0.6,
      open_price: 202,
      previous_close: 201.3,
      day_high: 203.4,
      day_low: 199.8,
      volume: 10342,
      status: 'ok',
      source: 'yahoo_finance',
      message: null,
      is_abnormal: false,
      abnormal_reason: null,
      fetched_at: '2026-03-18T11:25:00Z',
    },
  ],
  sparklines: {
    '0700.HK': [540, 545, 550.5],
    AAPL: [205, 203, 200.1],
  },
  selectedSymbol: '0700.HK',
  currentPeriod: '1D',
  klineData: {
    symbol: '0700.HK',
    interval: '1d',
    range: '6mo',
    stale: false,
    candles: [
      { time: '2026-03-18', open: 540, high: 552, low: 538, close: 550.5, volume: 21366376 },
      { time: '2026-03-19', open: 550, high: 556, low: 545, close: 554, volume: 20366376 },
    ],
    indicators: {
      ma5: [{ time: '2026-03-19', value: 548 }],
      ma10: [],
      ma20: [],
      ma60: [],
      macd: [{ time: '2026-03-19', dif: 1, dea: 0.8, histogram: 0.2 }],
      kdj: [],
      bollinger: [],
    },
    news_events: [{ time: '2026-03-19', items: [{ id: 101, title: 'Tencent update', sentiment: 'positive' }] }],
  },
  detailNews: [
    { id: 101, title: 'Tencent update', summary: 'AI expansion', source_name: 'Reuters', canonical_url: null, market: 'hk', sentiment_label: 'positive', published_at: '2026-03-19T10:00:00Z', fetched_at: '2026-03-19T10:05:00Z' },
  ],
  stale: false,
  loading: false,
  klineLoading: false,
  klineError: null,
  detailLoading: false,
  relatedLoading: false,
  createLoading: false,
  refreshLoading: false,
  createError: null,
  refreshError: null,
  candidateError: null,
  deleteLoadingSymbol: null,
  deleteError: null,
  loadCandidates: vi.fn(async () => undefined),
  loadWatchlist: vi.fn(async () => undefined),
  createWatchlist: vi.fn(async () => undefined),
  deleteWatchlist: vi.fn(async () => undefined),
  refreshMarketQuotes: vi.fn(async () => undefined),
  selectSymbol: vi.fn(async (symbol: string) => {
    watchlistStore.selectedSymbol = symbol;
  }),
  switchPeriod: vi.fn(async (period: string) => {
    watchlistStore.currentPeriod = period;
  }),
});

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push,
  }),
  useRoute: () => ({
    name: 'watchlist',
    params: {},
  }),
}));

vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    addSeries: () => ({ setData: vi.fn() }),
    remove: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn() }),
  }),
  LineSeries: Symbol('LineSeries'),
  CandlestickSeries: Symbol('CandlestickSeries'),
  HistogramSeries: Symbol('HistogramSeries'),
}));

vi.mock('../stores/watchlistStore', () => ({
  useWatchlistStore: () => watchlistStore,
}));

vi.mock('../stores/runtimeStatusStore', () => ({
  useRuntimeStatusStore: () => ({
    marketWorkerStatus: { name: 'market_quote_producer', status: 'degraded', last_quotes_count: 2 },
    streamStatus: null,
    usingMock: false,
    loadRuntimeStatus: vi.fn(async () => undefined),
  }),
}));

describe('WatchlistView', () => {
  beforeEach(() => {
    push.mockClear();
    watchlistStore.candidates = [
      { symbol: '0700.HK', market: 'hk', display_name: 'Tencent', aliases: ['腾讯'] },
      { symbol: 'BABA', market: 'us', display_name: 'Alibaba', aliases: ['阿里'] },
    ];
    watchlistStore.items = [
      { id: 1, symbol: '0700.HK', market: 'hk', display_name: 'Tencent', is_active: true, alert_threshold: 3, alert_mode: 'fixed' },
      { id: 2, symbol: 'AAPL', market: 'us', display_name: 'Apple', is_active: true, alert_threshold: 2, alert_mode: 'fixed' },
    ];
    watchlistStore.selectedSymbol = '0700.HK';
    watchlistStore.createError = null;
    watchlistStore.refreshError = null;
    watchlistStore.deleteError = null;
    watchlistStore.loadCandidates.mockClear();
    watchlistStore.loadWatchlist.mockClear();
    watchlistStore.createWatchlist.mockClear();
    watchlistStore.deleteWatchlist.mockClear();
    watchlistStore.refreshMarketQuotes.mockClear();
    watchlistStore.selectSymbol.mockClear();
    watchlistStore.switchPeriod.mockClear();
    watchlistStore.klineData.indicators.kdj = [];
    watchlistStore.klineData.indicators.bollinger = [];
  });

  it('renders the dashboard master-detail layout', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    expect(watchlistStore.loadCandidates).toHaveBeenCalled();
    expect(wrapper.find('[data-role="watchlist-dashboard"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="watchlist-sidebar"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="stock-detail-panel"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="kline-chart"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="trading-desk-news-feed"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="market-worker-status"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="market-refresh-action"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="trading-desk-summary"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="trading-desk-main"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="trading-desk-secondary"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Trading Dashboard');
    expect(wrapper.text()).toContain('Tencent');
    expect(wrapper.text()).toContain('0700.HK');
    expect(wrapper.text()).toContain('550.50');
    expect(wrapper.text()).toContain('+5.50');
    expect(wrapper.text()).toContain('+1.01%');
    expect(wrapper.text()).toContain('Open');
    expect(wrapper.text()).toContain('Prev Close');
    expect(wrapper.text()).toContain('High');
    expect(wrapper.text()).toContain('Low');
    expect(wrapper.text()).toContain('Volume');
    expect(wrapper.text()).toContain('Updated');
  });

  it('selects a stock card when the user clicks the sidebar item', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="stock-card-AAPL"]').trigger('click');

    expect(watchlistStore.selectSymbol).toHaveBeenCalledWith('AAPL');
    expect(push).toHaveBeenCalledWith({ name: 'watchlist-detail', params: { symbol: 'AAPL' } });
  });

  it('switches periods and disables empty indicators', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    expect(wrapper.get('[data-role="trading-desk-summary"]').get('[data-role="period-1W"]').exists()).toBe(true);
    await wrapper.get('[data-role="period-1W"]').trigger('click');

    expect(watchlistStore.switchPeriod).toHaveBeenCalledWith('1W');
    expect(wrapper.get('[data-role="indicator-KDJ"]').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[data-role="indicator-BOLL"]').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[data-role="indicator-MACD"]').attributes('disabled')).toBeUndefined();
  });

  it('keeps loading the dashboard when candidate lookup fails', async () => {
    watchlistStore.loadCandidates.mockRejectedValueOnce(new Error('candidate down'));

    mount(WatchlistView);
    await flushPromises();

    expect(watchlistStore.loadWatchlist).toHaveBeenCalled();
  });

  it('opens add modal and only submits after direct add', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="watchlist-open-add-modal"]').trigger('click');
    expect(wrapper.get('[data-role="watchlist-add-modal"]').attributes('aria-hidden')).toBe('false');

    await wrapper.get('[data-role="watchlist-add-search"]').setValue('Alibaba');
    await wrapper.get('[data-role="watchlist-candidate-BABA"]').trigger('click');

    expect(watchlistStore.createWatchlist).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain('Alibaba');

    await wrapper.get('[data-role="watchlist-add-submit"]').trigger('click');
    await flushPromises();

    expect(watchlistStore.createWatchlist).toHaveBeenCalledWith({
      symbol: 'BABA',
      market: 'us',
      display_name: 'Alibaba',
      alert_threshold: null,
      alert_mode: 'fixed',
    });
    expect(watchlistStore.selectSymbol).toHaveBeenCalledWith('BABA');
    expect(wrapper.get('[data-role="watchlist-add-modal"]').attributes('aria-hidden')).toBe('true');
  });

  it('passes advanced threshold when user expands advanced settings', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="watchlist-open-add-modal"]').trigger('click');
    await wrapper.get('[data-role="watchlist-add-search"]').setValue('Alibaba');
    await wrapper.get('[data-role="watchlist-candidate-BABA"]').trigger('click');
    await wrapper.get('[data-role="watchlist-add-advanced-toggle"]').trigger('click');
    await wrapper.get('[data-role="watchlist-add-threshold"]').setValue('8.5');
    await wrapper.get('[data-role="watchlist-add-submit"]').trigger('click');

    expect(watchlistStore.createWatchlist).toHaveBeenCalledWith({
      symbol: 'BABA',
      market: 'us',
      display_name: 'Alibaba',
      alert_threshold: 8.5,
      alert_mode: 'fixed',
    });
  });

  it('keeps the modal open and preserves selection after add failure', async () => {
    watchlistStore.createWatchlist.mockRejectedValueOnce(new Error('create failed'));
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="watchlist-open-add-modal"]').trigger('click');
    await wrapper.get('[data-role="watchlist-add-search"]').setValue('Alibaba');
    await wrapper.get('[data-role="watchlist-candidate-BABA"]').trigger('click');
    await wrapper.get('[data-role="watchlist-add-submit"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-role="watchlist-add-modal"]').attributes('aria-hidden')).toBe('false');
    expect(wrapper.get('[data-role="watchlist-add-selected-symbol"]').text()).toContain('BABA');
  });

  it('keeps refresh errors inside the view state instead of leaking promise rejections', async () => {
    watchlistStore.refreshMarketQuotes.mockImplementationOnce(async () => {
      watchlistStore.refreshError = '手动刷新行情失败，请稍后重试';
      throw new Error('refresh failed');
    });
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="market-refresh-action"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('手动刷新行情失败，请稍后重试');
  });

  it('keeps delete errors inside the view state instead of leaking promise rejections', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    watchlistStore.deleteWatchlist.mockImplementationOnce(async () => {
      watchlistStore.deleteError = '删除自选股失败，请检查后端服务';
      throw new Error('delete failed');
    });
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="stock-card-AAPL"] button').trigger('click');
    await flushPromises();

    expect(watchlistStore.deleteWatchlist).toHaveBeenCalledWith('AAPL');
    expect(wrapper.text()).toContain('删除自选股失败，请检查后端服务');
  });

  it('links event chips and news timeline highlights in both directions', async () => {
    watchlistStore.klineData.news_events = [
      { time: '2026-03-19', items: [{ id: 101, title: 'Tencent update', sentiment: 'positive' }] },
      { time: '2026-03-20', items: [{ id: 102, title: 'Tencent follow-up', sentiment: 'neutral' }] },
    ];
    watchlistStore.detailNews = [
      { id: 101, title: 'Tencent update', summary: 'AI expansion', source_name: 'Reuters', canonical_url: null, market: 'hk', sentiment_label: 'positive', published_at: '2026-03-19T10:00:00Z', fetched_at: '2026-03-19T10:05:00Z' },
      { id: 102, title: 'Tencent follow-up', summary: 'New cloud demand', source_name: 'Bloomberg', canonical_url: null, market: 'hk', sentiment_label: 'neutral', published_at: '2026-03-20T03:00:00Z', fetched_at: '2026-03-20T03:05:00Z' },
    ];
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="kline-event-chip-2026-03-19"]').trigger('click');
    expect(wrapper.get('[data-role="trading-desk-news-item-101"]').attributes('data-highlighted')).toBe('true');
    expect(wrapper.get('[data-role="trading-desk-news-item-102"]').attributes('data-highlighted')).toBe('false');

    await wrapper.get('[data-role="trading-desk-news-item-102"]').trigger('click');
    expect(wrapper.get('[data-role="kline-event-chip-2026-03-20"]').attributes('data-active')).toBe('true');
  });
});
