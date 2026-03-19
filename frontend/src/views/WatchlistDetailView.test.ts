import { mount } from '@vue/test-utils';
import { computed, reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WatchlistDetailView from './WatchlistDetailView.vue';

const push = vi.fn();
const route = reactive({
  params: {
    symbol: '0700.HK',
  },
});

const watchlistStore = reactive({
  stale: false,
  detailLoading: false,
  relatedLoading: false,
  quoteDetail: {
    symbol: '0700.HK',
    market: 'hk',
    display_name: 'Tencent',
    provider_symbol: '0700.HK',
    price: 545,
    change_amount: -5,
    change_percent: -0.91,
    open_price: 546.5,
    previous_close: 550,
    day_high: 550.5,
    day_low: 542.5,
    volume: 9371872,
    fetched_at: '2026-03-18T05:02:00Z',
    status: 'ok',
    source: 'yahoo_finance',
    message: null,
  },
  relatedNews: {
    '0700.HK': [
      {
        id: 1,
        title: 'Tencent expands enterprise AI product suite',
        summary: 'Tencent pushes deeper into enterprise AI workflows and cloud integration.',
        source_name: 'Reuters',
        market: 'hk',
        sentiment_label: 'positive',
        canonical_url: null,
        published_at: '2026-03-18T00:40:00Z',
        fetched_at: '2026-03-18T00:45:00Z',
      },
    ],
  } as Record<string, any[]>,
  loadQuoteDetail: vi.fn(async () => undefined),
  loadRelatedNews: vi.fn(async () => undefined),
});

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({
    push,
  }),
}));

vi.mock('../stores/watchlistStore', () => ({
  useWatchlistStore: () => watchlistStore,
}));

describe('WatchlistDetailView', () => {
  beforeEach(() => {
    push.mockReset();
    watchlistStore.loadQuoteDetail.mockClear();
    watchlistStore.loadRelatedNews.mockClear();
  });

  it('renders metric and related news cards as terminal surfaces', () => {
    const wrapper = mount(WatchlistDetailView);

    expect(wrapper.find('[data-role="watchlist-detail-grid"]').exists()).toBe(true);
    expect(wrapper.find('[data-surface="terminal-metric-card"]').exists()).toBe(true);
    expect(wrapper.find('[data-surface="terminal-related-card"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="price-change"]').classes()).toContain('text-negative');
  });
});
