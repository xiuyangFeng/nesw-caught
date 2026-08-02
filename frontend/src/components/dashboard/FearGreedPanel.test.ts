import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import FearGreedPanel from './FearGreedPanel.vue';
import type { MarketOverview } from '../../types/api';

const marketOverviewStore = reactive({
  overview: null as MarketOverview | null,
  loading: false,
  error: null as string | null,
});

vi.mock('../../stores/marketOverviewStore', () => ({
  useMarketOverviewStore: () => marketOverviewStore,
}));

const overviewFixture: MarketOverview = {
  generated_at: '2026-08-02T08:00:00Z',
  markets: [
    {
      market: 'us',
      display_name: '美股',
      is_open: true,
      indices: [],
      quant_sentiment: {
        score: 0.4,
        label: 'greed',
        inputs: { avg_change_percent: 0.82, vix: 18.4, adv_ratio: null },
      },
      boards: {
        status: 'ok',
        stale: false,
        source: 'preset_etf',
        items: [
          {
            code: 'SPY',
            name: '标普ETF',
            price: 500,
            change_percent: 0.8,
            advance_count: 30,
            decline_count: 10,
            flat_count: 0,
            net_inflow: null,
            fetched_at: null,
          },
        ],
      },
      news_sentiment: { status: 'ok', score: 0.31, sample_count: 12, top_signals: [] },
    },
    {
      market: 'cn',
      display_name: 'A股',
      is_open: false,
      indices: [],
      quant_sentiment: null,
      boards: { status: 'fetch_failed', stale: false, source: 'eastmoney', items: [], message: '超时' },
      news_sentiment: { status: 'insufficient_data', score: null, sample_count: 0, top_signals: [] },
    },
  ],
};

describe('FearGreedPanel', () => {
  beforeEach(() => {
    marketOverviewStore.overview = null;
    marketOverviewStore.loading = false;
    marketOverviewStore.error = null;
  });

  it('renders one card per market with gauge value, label and inputs', () => {
    marketOverviewStore.overview = overviewFixture;

    const wrapper = mount(FearGreedPanel);

    expect(wrapper.find('[data-role="fear-greed-card-us"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="fear-greed-card-cn"]').exists()).toBe(true);

    const usCard = wrapper.find('[data-role="fear-greed-card-us"]');
    // score 0.4 -> (0.4 + 1) / 2 * 100 = 70
    expect(usCard.find('[data-role="fear-greed-value"]').text()).toBe('70');
    expect(usCard.find('[data-role="fear-greed-label"]').text()).toBe('贪婪');
    expect(usCard.text()).toContain('VIX');
    expect(usCard.text()).toContain('18.4');
    expect(usCard.text()).toContain('0.82%');
    expect(usCard.find('[data-role="market-open-badge"]').text()).toBe('开盘中');
  });

  it('degrades gracefully when quant sentiment or breadth data is missing', () => {
    marketOverviewStore.overview = overviewFixture;

    const wrapper = mount(FearGreedPanel);
    const cnCard = wrapper.find('[data-role="fear-greed-card-cn"]');

    expect(cnCard.find('[data-role="fear-greed-value"]').text()).toBe('--');
    expect(cnCard.find('[data-role="fear-greed-label"]').text()).toBe('数据不足');
    expect(cnCard.find('[data-role="breadth-empty"]').exists()).toBe(true);
    expect(cnCard.find('[data-role="news-sentiment-row"]').text()).toContain('样本不足');
    expect(cnCard.find('[data-role="market-open-badge"]').text()).toBe('已闭市');
  });

  it('renders advance/decline breadth bar with proportional widths', () => {
    marketOverviewStore.overview = overviewFixture;

    const wrapper = mount(FearGreedPanel);
    const usCard = wrapper.find('[data-role="fear-greed-card-us"]');

    const advance = usCard.find('[data-role="breadth-advance"]');
    const decline = usCard.find('[data-role="breadth-decline"]');
    expect(advance.attributes('style')).toContain('width: 75%');
    expect(decline.attributes('style')).toContain('width: 25%');
    expect(usCard.text()).toContain('涨 30');
    expect(usCard.text()).toContain('跌 10');
    expect(usCard.find('[data-role="news-sentiment-row"]').text()).toContain('0.31');
  });

  it('shows empty state when overview has no markets', () => {
    const wrapper = mount(FearGreedPanel);

    expect(wrapper.find('[data-role="fear-greed-empty"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="fear-greed-grid"]').exists()).toBe(false);
  });
});
