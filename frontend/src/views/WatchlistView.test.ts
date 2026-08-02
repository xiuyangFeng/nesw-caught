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

vi.mock('../api/client', () => ({
  apiClient: {
    searchMarketSymbols: vi.fn(async (q: string) => {
      const candidates = [
        { symbol: '0700.HK', market: 'hk', display_name: 'Tencent', aliases: ['腾讯'] },
        { symbol: 'BABA', market: 'us', display_name: 'Alibaba', aliases: ['阿里'] },
        { symbol: '600519.SH', market: 'cn', display_name: '贵州茅台', aliases: ['茅台', '600519'] },
      ];
      const filtered = candidates.filter(c =>
        c.symbol.toLowerCase().includes(q.toLowerCase()) ||
        c.display_name.toLowerCase().includes(q.toLowerCase()) ||
        (c.aliases && c.aliases.some(a => a.toLowerCase().includes(q.toLowerCase())))
      );
      return { data: filtered };
    }),
  },
}));

import WatchlistView from './WatchlistView.vue';
const push = vi.fn();

const watchlistStore = reactive({
  candidates: [
    { symbol: '0700.HK', market: 'hk', display_name: 'Tencent', aliases: ['腾讯'] },
    { symbol: 'BABA', market: 'us', display_name: 'Alibaba', aliases: ['阿里'] },
    { symbol: '600519.SH', market: 'cn', display_name: '贵州茅台', aliases: ['茅台', '600519'] },
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
  refreshError: null as string | null,
  candidateError: null,
  deleteLoadingSymbol: null,
  deleteError: null as string | null,
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

const marketOverviewStore = reactive({
  overview: null as any,
  indexConfigs: [],
  loading: false,
  error: null as string | null,
  usingMock: false,
  configSaving: false,
  configError: null as string | null,
  loadOverview: vi.fn(async () => undefined),
  startAutoRefresh: vi.fn(),
  stopAutoRefresh: vi.fn(),
  loadIndexConfig: vi.fn(async () => undefined),
  createIndexConfig: vi.fn(async () => undefined),
  updateIndexConfig: vi.fn(async () => undefined),
  deleteIndexConfig: vi.fn(async () => undefined),
});

vi.mock('../stores/marketOverviewStore', () => ({
  useMarketOverviewStore: () => marketOverviewStore,
}));

describe('WatchlistView', () => {
  beforeEach(() => {
    push.mockClear();
    watchlistStore.candidates = [
      { symbol: '0700.HK', market: 'hk', display_name: 'Tencent', aliases: ['腾讯'] },
      { symbol: 'BABA', market: 'us', display_name: 'Alibaba', aliases: ['阿里'] },
      { symbol: '600519.SH', market: 'cn', display_name: '贵州茅台', aliases: ['茅台', '600519'] },
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
    marketOverviewStore.overview = null;
    marketOverviewStore.error = null;
    marketOverviewStore.loading = false;
    marketOverviewStore.loadOverview.mockClear();
    marketOverviewStore.startAutoRefresh.mockClear();
    marketOverviewStore.stopAutoRefresh.mockClear();
    marketOverviewStore.loadIndexConfig.mockClear();
  });

  it('renders the standalone watchlist list page without the detail panel', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    expect(watchlistStore.loadCandidates).toHaveBeenCalled();
    expect(wrapper.find('[data-role="watchlist-dashboard"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="watchlist-sidebar"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="stock-detail-panel"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="watchlist-toolbar"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="watchlist-compact-list"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="market-worker-status"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="market-refresh-action"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Trading Dashboard');
    expect(wrapper.get('[data-role="watchlist-open-add-modal"]').text()).toBe('添加');
    expect(wrapper.get('[data-role="stock-card-0700.HK"]').attributes('data-density')).toBe('compact');
    expect(wrapper.text()).toContain('Tencent');
    expect(wrapper.text()).toContain('0700.HK');
  });

  it('selects a stock card when the user clicks the sidebar item', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="stock-card-AAPL"]').trigger('click');

    expect(push).toHaveBeenCalledWith({ name: 'watchlist-detail', params: { symbol: 'AAPL' } });
    expect(watchlistStore.selectSymbol).not.toHaveBeenCalled();
  });

  it('keeps loading the dashboard when candidate lookup fails', async () => {
    watchlistStore.loadCandidates.mockRejectedValueOnce(new Error('candidate down'));

    mount(WatchlistView);
    await flushPromises();

    expect(watchlistStore.loadWatchlist).toHaveBeenCalled();
  });

  it('adds an a-share candidate from the modal and routes to its detail page', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="watchlist-open-add-modal"]').trigger('click');
    await wrapper.get('[data-role="watchlist-add-search"]').setValue('600519');
    await new Promise((resolve) => setTimeout(resolve, 0));
    await flushPromises();
    await wrapper.get('[data-role="watchlist-candidate-600519.SH"]').trigger('click');
    await wrapper.get('[data-role="watchlist-add-submit"]').trigger('click');
    await flushPromises();

    expect(watchlistStore.createWatchlist).toHaveBeenCalledWith({
      symbol: '600519.SH',
      market: 'cn',
      display_name: '贵州茅台',
      alert_threshold: null,
      alert_mode: 'fixed',
    });
    expect(push).toHaveBeenCalledWith({ name: 'watchlist-detail', params: { symbol: '600519.SH' } });
  });

  it('opens add modal and only submits after direct add', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="watchlist-open-add-modal"]').trigger('click');
    expect(wrapper.get('[data-role="watchlist-add-modal"]').attributes('aria-hidden')).toBe('false');
    expect(wrapper.text()).toContain('添加自选');

    await wrapper.get('[data-role="watchlist-add-search"]').setValue('Alibaba');
    await new Promise((resolve) => setTimeout(resolve, 0));
    await flushPromises();
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
    expect(watchlistStore.selectSymbol).not.toHaveBeenCalled();
    expect(wrapper.get('[data-role="watchlist-add-modal"]').attributes('aria-hidden')).toBe('true');
  });

  it('passes advanced threshold when user expands advanced settings', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    await wrapper.get('[data-role="watchlist-open-add-modal"]').trigger('click');
    await wrapper.get('[data-role="watchlist-add-search"]').setValue('Alibaba');
    await new Promise((resolve) => setTimeout(resolve, 0));
    await flushPromises();
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
    await new Promise((resolve) => setTimeout(resolve, 0));
    await flushPromises();
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

  it('mounts the market overview panel above the tabs and starts the 60s auto refresh', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    const panel = wrapper.get('[data-role="market-overview-panel"]');
    const tabs = wrapper.get('[data-role="watchlist-tabs"]');
    expect(panel.element.compareDocumentPosition(tabs.element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(marketOverviewStore.loadOverview).toHaveBeenCalledTimes(1);
    expect(marketOverviewStore.startAutoRefresh).toHaveBeenCalledTimes(1);
  });

  it('renders one overview card per market when the overview payload is available', async () => {
    marketOverviewStore.overview = {
      generated_at: '2026-08-02T08:00:00Z',
      markets: ['us', 'cn', 'kr', 'jp', 'eu'].map((key) => ({
        market: key,
        display_name: `市场-${key}`,
        is_open: false,
        indices: [],
        quant_sentiment: null,
        boards: { status: 'none', stale: false, source: 'none', items: [] },
        news_sentiment: null,
      })),
    };

    const wrapper = mount(WatchlistView);
    await flushPromises();

    expect(wrapper.findAll('[data-role^="market-overview-card-"]')).toHaveLength(5);
    expect(wrapper.text()).toContain('市场-jp');
  });

  it('stops the overview auto refresh timer when the view unmounts', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    wrapper.unmount();

    expect(marketOverviewStore.stopAutoRefresh).toHaveBeenCalledTimes(1);
  });

  it('keeps the tab area intact when the overview fails to load', async () => {
    marketOverviewStore.error = '市场总览加载失败';

    const wrapper = mount(WatchlistView);
    await flushPromises();

    expect(wrapper.get('[data-role="market-overview-panel"]').text()).toContain('市场总览加载失败');
    expect(wrapper.find('[data-role="watchlist-tabs"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="watchlist-sidebar"]').exists()).toBe(true);
  });

});
