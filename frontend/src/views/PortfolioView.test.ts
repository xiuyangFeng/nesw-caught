import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { PortfolioSummary } from '../types/api';
import PortfolioView from './PortfolioView.vue';

const { getPortfolio } = vi.hoisted(() => ({
  getPortfolio: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: {
    getPortfolio,
  },
}));

vi.mock('vue-router', () => ({
  RouterLink: {
    name: 'RouterLink',
    props: ['to'],
    template: '<a :href="typeof to === \'string\' ? to : to?.path"><slot /></a>',
  },
}));

const summary: PortfolioSummary = {
  generated_at: '2026-07-14T05:00:00Z',
  position_count: 2,
  priced_position_count: 2,
  total_market_value: 96000,
  total_cost_basis: 95000,
  total_unrealized_pnl: 1000,
  total_unrealized_pnl_percent: 1.05,
  positions: [
    {
      symbol: 'AAPL',
      market: 'us',
      display_name: 'Apple',
      position_size: 100,
      average_cost: 150,
      current_price: 200,
      change_percent: 1.2,
      price_status: 'ok',
      price_message: null,
      quote_fetched_at: '2026-07-14T04:59:00Z',
      market_value: 20000,
      cost_basis: 15000,
      unrealized_pnl: 5000,
      unrealized_pnl_percent: 33.3,
      weight: 0.21,
    },
    {
      symbol: '0700.HK',
      market: 'hk',
      display_name: 'Tencent',
      position_size: 200,
      average_cost: 400,
      current_price: 380,
      change_percent: -0.5,
      price_status: 'ok',
      price_message: null,
      quote_fetched_at: '2026-07-14T04:59:00Z',
      market_value: 76000,
      cost_basis: 80000,
      unrealized_pnl: -4000,
      unrealized_pnl_percent: -5,
      weight: 0.79,
    },
  ],
  weighted_news: [
    {
      news_item: {
        id: 5,
        title: 'Apple 新品发布利好',
        summary: '摘要',
        source_name: 'Reuters',
        canonical_url: null,
        market: 'us',
        sentiment_label: 'positive',
        published_at: '2026-07-14T02:00:00Z',
        fetched_at: '2026-07-14T02:05:00Z',
      },
      symbols: ['AAPL'],
      sentiment_score: 0.8,
      signed_impact: 0.12,
      impact_score: 0.12,
    },
  ],
};

describe('PortfolioView', () => {
  beforeEach(() => {
    getPortfolio.mockReset();
    getPortfolio.mockResolvedValue({ data: summary, degraded: false });
  });

  it('renders summary cards, positions and weighted news', async () => {
    const wrapper = mount(PortfolioView);
    await flushPromises();

    expect(getPortfolio).toHaveBeenCalled();
    expect(wrapper.find('[data-role="portfolio-summary"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('96,000');
    expect(wrapper.text()).toContain('+1,000');

    const rows = wrapper.findAll('[data-role="portfolio-position-row"]');
    expect(rows).toHaveLength(2);
    expect(wrapper.text()).toContain('Apple');
    expect(wrapper.text()).toContain('Tencent');

    expect(wrapper.find('[data-role="portfolio-weighted-news"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Apple 新品发布利好');
  });

  it('shows the no-holdings state when there are no positions', async () => {
    getPortfolio.mockResolvedValue({
      data: { ...summary, position_count: 0, positions: [], weighted_news: [] },
      degraded: false,
    });

    const wrapper = mount(PortfolioView);
    await flushPromises();

    expect(wrapper.text()).toContain('尚无持仓');
    expect(wrapper.find('[data-role="portfolio-positions"]').exists()).toBe(false);
  });

  it('shows an error message and does not crash when the portfolio API fails', async () => {
    getPortfolio.mockRejectedValue(new Error('network down'));

    const wrapper = mount(PortfolioView);
    await flushPromises();

    expect(wrapper.text()).toContain('组合数据加载失败，请检查后端服务');
    expect(wrapper.find('[data-role="portfolio-summary"]').exists()).toBe(false);
  });

  it('reloads portfolio data when the refresh button is clicked', async () => {
    const wrapper = mount(PortfolioView);
    await flushPromises();
    expect(getPortfolio).toHaveBeenCalledTimes(1);

    await wrapper.get('[data-role="portfolio-refresh"]').trigger('click');
    await flushPromises();

    expect(getPortfolio).toHaveBeenCalledTimes(2);
  });
});
