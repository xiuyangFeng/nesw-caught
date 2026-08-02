import { mount } from '@vue/test-utils';
import { nextTick, reactive } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import MarketTickerStrip from './MarketTickerStrip.vue';
import type { MarketOverview } from '../../types/api';

const marketOverviewStore = reactive({
  overview: null as MarketOverview | null,
});

vi.mock('../../stores/marketOverviewStore', () => ({
  useMarketOverviewStore: () => marketOverviewStore,
}));

function buildOverview(spxChange: number): MarketOverview {
  return {
    generated_at: '2026-08-02T08:00:00Z',
    markets: [
      {
        market: 'us',
        display_name: '美股',
        is_open: true,
        indices: [
          {
            symbol: '^GSPC',
            display_name: '标普500',
            kind: 'index',
            price: 5123.45,
            change_percent: spxChange,
            previous_close: 5100,
            status: 'ok',
            fetched_at: null,
          },
          {
            symbol: '^VIX',
            display_name: '波动率指数',
            kind: 'index',
            price: 18.4,
            change_percent: -1.2,
            previous_close: 18.6,
            status: 'ok',
            fetched_at: null,
          },
          {
            symbol: '^IXIC',
            display_name: '纳斯达克',
            kind: 'index',
            price: null,
            change_percent: null,
            previous_close: null,
            status: 'unavailable',
            fetched_at: null,
          },
        ],
        quant_sentiment: null,
        boards: { status: 'none', stale: false, source: 'none', items: [] },
        news_sentiment: null,
      },
    ],
  };
}

describe('MarketTickerStrip', () => {
  beforeEach(() => {
    marketOverviewStore.overview = null;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders nothing when there are no indices', () => {
    const wrapper = mount(MarketTickerStrip);

    expect(wrapper.find('[data-role="market-ticker-strip"]').exists()).toBe(false);
  });

  it('renders index quotes duplicated for the seamless marquee, excluding ^VIX', () => {
    marketOverviewStore.overview = buildOverview(0.5);

    const wrapper = mount(MarketTickerStrip);

    // 列表渲染两份实现无缝滚动
    expect(wrapper.findAll('[data-role="ticker-item-us:^GSPC"]')).toHaveLength(2);
    expect(wrapper.find('[data-role="ticker-item-us:^VIX"]').exists()).toBe(false);

    const item = wrapper.find('[data-role="ticker-item-us:^GSPC"]');
    expect(item.text()).toContain('标普500');
    expect(item.text()).toContain('5,123.45');
    expect(item.find('[data-role="ticker-change"]').text()).toBe('+0.50%');
    expect(item.find('[data-role="ticker-change"]').classes()).toContain('text-positive');
  });

  it('shows placeholder for unavailable indices', () => {
    marketOverviewStore.overview = buildOverview(0.5);

    const wrapper = mount(MarketTickerStrip);

    const item = wrapper.find('[data-role="ticker-item-us:^IXIC"]');
    expect(item.find('[data-role="ticker-unavailable"]').exists()).toBe(true);
    expect(item.find('[data-role="ticker-price"]').exists()).toBe(false);
  });

  it('flashes the item when change percent moves', async () => {
    marketOverviewStore.overview = buildOverview(0.5);
    const wrapper = mount(MarketTickerStrip);

    marketOverviewStore.overview = buildOverview(0.8);
    await nextTick();

    const item = wrapper.find('[data-role="ticker-item-us:^GSPC"]');
    expect(item.attributes('class')).toContain('bg-[var(--positive-soft)]');
    expect(item.find('[data-role="ticker-change"]').text()).toBe('+0.80%');
  });

  it('clears pending flash timers when the ticker strip unmounts', async () => {
    vi.useFakeTimers();
    marketOverviewStore.overview = buildOverview(0.5);
    const wrapper = mount(MarketTickerStrip);

    marketOverviewStore.overview = buildOverview(0.8);
    await nextTick();
    const pendingTimerCount = vi.getTimerCount();
    expect(pendingTimerCount).toBeGreaterThan(0);

    wrapper.unmount();

    expect(vi.getTimerCount()).toBeLessThan(pendingTimerCount);
  });
});
