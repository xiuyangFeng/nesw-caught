import { mount, flushPromises } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WatchlistView from './WatchlistView.vue';

const push = vi.fn();

const watchlistStore = reactive({
  candidates: [
    { symbol: '0700.HK', market: 'hk', display_name: 'Tencent', aliases: ['腾讯', '腾讯控股'] },
    { symbol: 'TME', market: 'us', display_name: 'Tencent Music', aliases: ['腾讯音乐'] },
    { symbol: 'AAPL', market: 'us', display_name: 'Apple', aliases: ['苹果'] },
  ],
  items: [
    { id: 1, symbol: '0700.HK', market: 'hk', display_name: 'Tencent', is_active: true, alert_threshold: 3, alert_mode: 'fixed' },
  ],
  quotes: [],
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
  lastManualRefreshResult: {
    quotes_count: 1,
    symbols: ['0700.HK'],
    triggered_at: '2026-03-23T06:00:00Z',
  },
  relatedNews: {},
  selectedSymbol: '0700.HK',
  stale: false,
  loading: false,
  relatedLoading: false,
  detailLoading: false,
  createLoading: false,
  refreshLoading: false,
  createError: null,
  refreshError: null,
  candidateError: null,
  deleteLoadingSymbol: null,
  deleteError: null,
  loadCandidates: vi.fn(async () => undefined),
  loadWatchlist: vi.fn(async () => undefined),
  loadRelatedNews: vi.fn(async () => undefined),
  createWatchlist: vi.fn(async () => undefined),
  refreshMarketQuotes: vi.fn(async () => undefined),
  deleteWatchlist: vi.fn(async () => undefined),
});

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push,
  }),
}));

vi.mock('../stores/watchlistStore', () => ({
  useWatchlistStore: () => watchlistStore,
}));

describe('WatchlistView', () => {
  beforeEach(() => {
    push.mockReset();
    watchlistStore.loadCandidates.mockClear();
    watchlistStore.loadWatchlist.mockClear();
    watchlistStore.loadRelatedNews.mockClear();
    watchlistStore.createWatchlist.mockClear();
    watchlistStore.refreshMarketQuotes.mockClear();
    watchlistStore.deleteWatchlist.mockClear();
  });

  it('renders the merged search-add toolbar and shows candidate results', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    expect(watchlistStore.loadCandidates).toHaveBeenCalled();
    expect(wrapper.find('[data-role="watchlist-layout"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Control Station');
    expect(wrapper.find('[data-role="watchlist-shell"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="related-news-shell"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="market-worker-status"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('market_quote_producer');
    expect(wrapper.text()).toContain('provider timeout');
    expect(wrapper.text()).toContain('最近手动刷新');
    expect(wrapper.text()).toContain('0700.HK');
    expect(wrapper.find('[data-role="market-refresh-action"]').exists()).toBe(true);
    const searchInput = wrapper.get('input[placeholder="输入股票代码、中文名或英文名"]');
    await searchInput.setValue('腾');

    expect(wrapper.text()).toContain('Tencent');
    expect(wrapper.text()).toContain('Tencent Music');
    expect(wrapper.text()).toContain('已添加');
    expect(wrapper.find('[data-role="candidate-list"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="watchlist-action"]').exists()).toBe(true);
  });
});
