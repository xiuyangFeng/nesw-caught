import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

vi.mock('./KlineChart.vue', () => ({
  default: {
    props: ['highlightedEventTime'],
    emits: ['focusNews'],
    template: `
      <section data-role="kline-chart-stub">
        <div data-role="kline-highlighted-time">{{ highlightedEventTime ?? '' }}</div>
        <button data-role="kline-event-chip-2026-03-19" @click="$emit('focusNews', { time: '2026-03-19', items: [{ id: 101, title: 'Apple update', sentiment: 'neutral' }] })">
          event
        </button>
      </section>
    `,
  },
}));

vi.mock('./RelatedNewsSidebar.vue', () => ({
  default: {
    props: ['items', 'highlightedEventTime'],
    emits: ['focusNews'],
    template: `
      <section data-role="trading-desk-news-feed">
        <div data-role="news-highlighted-time">{{ highlightedEventTime ?? '' }}</div>
        <button
          v-for="item in items"
          :key="item.id"
          :data-role="\`trading-desk-news-item-\${item.id}\`"
          :data-highlighted="highlightedEventTime === (item.published_at ?? item.fetched_at).slice(0, 10) ? 'true' : 'false'"
          @click="$emit('focusNews', item)"
        >
          {{ item.title }}
        </button>
      </section>
    `,
  },
}));

import StockDetailPanel from './StockDetailPanel.vue';

describe('StockDetailPanel', () => {
  it('shows settings popover controls and preserves chart/news highlighting linkage', async () => {
    const wrapper = mount(StockDetailPanel, {
      props: {
        quote: {
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
        klineData: {
          symbol: 'AAPL',
          interval: '1d',
          range: '6mo',
          stale: false,
          candles: [{ time: '2026-03-18', open: 199, high: 202, low: 198, close: 200.1, volume: 10342 }],
          indicators: {
            ma5: [],
            ma10: [],
            ma20: [],
            ma60: [],
            macd: [],
            kdj: [],
            bollinger: [],
          },
          news_events: [{ time: '2026-03-19', items: [{ id: 101, title: 'Apple update', sentiment: 'neutral' }] }],
        },
        detailNews: [
          {
            id: 101,
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
        currentPeriod: '1D',
        klineLoading: false,
        klineError: null,
      },
    });

    await wrapper.get('[data-role="watchlist-settings-trigger"]').trigger('click');

    expect(wrapper.get('[data-role="watchlist-settings-popover"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="watchlist-settings-scroll"]').classes()).toContain('overflow-y-auto');
    expect(wrapper.get('[data-role="period-1D"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="watchlist-indicator-MACD"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="watchlist-indicator-KDJ"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="watchlist-indicator-BOLL"]').exists()).toBe(true);

    await wrapper.get('[data-role="kline-event-chip-2026-03-19"]').trigger('click');
    expect(wrapper.get('[data-role="trading-desk-news-item-101"]').attributes('data-highlighted')).toBe('true');

    await wrapper.get('[data-role="trading-desk-news-item-101"]').trigger('click');
    expect(wrapper.get('[data-role="kline-highlighted-time"]').text()).toBe('2026-03-19');
  });
});
