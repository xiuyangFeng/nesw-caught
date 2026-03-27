import { mount, flushPromises } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { HttpError } from '../api/http';
import WatchlistDetailView from './WatchlistDetailView.vue';

const push = vi.fn();

const watchlistStore = reactive({
  quoteDetail: {
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
  relatedNews: {
    AAPL: [
      {
        id: 1,
        title: 'Apple update',
        summary: 'Product news',
        source_name: 'Reuters',
        canonical_url: null,
        market: 'us',
        sentiment_label: 'neutral',
        published_at: '2026-03-19T10:00:00Z',
        fetched_at: '2026-03-19T10:05:00Z',
      },
    ],
  },
  detailNews: [
    {
      id: 1,
      title: 'Apple update',
      summary: 'Product news',
      source_name: 'Reuters',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-03-19T10:00:00Z',
      fetched_at: '2026-03-19T10:05:00Z',
    },
  ],
  klineData: {
    symbol: 'AAPL',
    interval: '1d',
    range: '6mo',
    stale: false,
    candles: [
      { time: '2026-03-18', open: 199, high: 202, low: 198, close: 200.1, volume: 10342 },
    ],
    indicators: {
      ma5: [],
      ma10: [],
      ma20: [],
      ma60: [],
      macd: [],
      kdj: [],
      bollinger: [],
    },
    news_events: [{ time: '2026-03-19', items: [{ id: 1, title: 'Apple update', sentiment: 'neutral' }] }],
  },
  currentPeriod: '1D',
  klineLoading: false,
  klineError: null,
  detailLoading: false,
  relatedLoading: false,
  stale: false,
  loadQuoteDetail: vi.fn(async () => undefined),
  loadRelatedNews: vi.fn(async () => undefined),
  selectSymbol: vi.fn(async () => undefined),
});

const routeState = reactive({
  params: { symbol: 'AAPL' as string | undefined },
});

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push,
  }),
  useRoute: () => routeState,
}));

vi.mock('../stores/watchlistStore', () => ({
  useWatchlistStore: () => watchlistStore,
}));

vi.mock('../components/common/StaleBadge.vue', () => ({
  default: {
    template: '<div data-role="stale-badge"></div>',
  },
}));

vi.mock('../components/watchlist/KlineChart.vue', () => ({
  default: {
    template: '<section data-role="kline-chart-stub"></section>',
  },
}));

vi.mock('../components/watchlist/IndicatorChart.vue', () => ({
  default: {
    template: '<section data-role="indicator-chart-stub"></section>',
  },
}));

vi.mock('../components/watchlist/RelatedNewsSidebar.vue', () => ({
  default: {
    props: ['items', 'highlightedEventTime'],
    template:
      '<section data-role="trading-desk-news-feed"><button v-for="item in items" :key="item.id" :data-role="`trading-desk-news-item-${item.id}`">{{ item.title }}</button></section>',
  },
}));

describe('WatchlistDetailView', () => {
  beforeEach(() => {
    push.mockClear();
    routeState.params.symbol = 'AAPL';
    watchlistStore.loadQuoteDetail.mockClear();
    watchlistStore.loadRelatedNews.mockClear();
    watchlistStore.selectSymbol.mockClear();
  });

  it('loads the dedicated detail page data for the route symbol', async () => {
    const wrapper = mount(WatchlistDetailView);
    await flushPromises();

    expect(watchlistStore.selectSymbol).toHaveBeenCalledWith('AAPL');
    expect(watchlistStore.loadQuoteDetail).toHaveBeenCalledWith('AAPL');
    expect(watchlistStore.loadRelatedNews).toHaveBeenCalledWith('AAPL');
    expect(wrapper.find('[data-role="watchlist-detail-main"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('返回自选股总览');
  });

  it('renders the dedicated detail layout with news below kline and settings popover entry', async () => {
    const wrapper = mount(WatchlistDetailView);
    await flushPromises();

    expect(wrapper.find('[data-role="trading-desk-main"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="watchlist-detail-news"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="watchlist-settings-trigger"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="indicator-chart-stub"]').exists()).toBe(false);

    await wrapper.get('[data-role="watchlist-settings-trigger"]').trigger('click');

    expect(wrapper.find('[data-role="watchlist-settings-popover"]').exists()).toBe(true);
  });

  it('falls back to the watchlist list when the route symbol is missing', async () => {
    routeState.params.symbol = undefined;

    mount(WatchlistDetailView);
    await flushPromises();

    expect(push).toHaveBeenCalledWith({ name: 'watchlist' });
    expect(watchlistStore.selectSymbol).not.toHaveBeenCalled();
    expect(watchlistStore.loadQuoteDetail).not.toHaveBeenCalled();
    expect(watchlistStore.loadRelatedNews).not.toHaveBeenCalled();
  });

  it('does not leave the detail page on non-404 loading errors', async () => {
    watchlistStore.loadQuoteDetail.mockRejectedValueOnce(new HttpError('temporary failure', 500));

    const wrapper = mount(WatchlistDetailView);
    await flushPromises();

    expect(push).not.toHaveBeenCalledWith({ name: 'watchlist' });
    expect(wrapper.find('[data-role="watchlist-detail-main"]').exists()).toBe(true);
  });
});
