import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

vi.mock('./ResearchBriefPanel.vue', () => ({
  default: {
    props: ['researchBrief'],
    template: `
      <section data-role="research-brief-panel-stub">
        <div data-role="research-brief-symbol">{{ researchBrief?.symbol ?? '' }}</div>
      </section>
    `,
  },
}));

vi.mock('./KlineChart.vue', () => ({
  default: {
    props: ['highlightedEventTime', 'currentPeriod'],
    emits: ['focusNews', 'switchPeriod'],
    template: `
      <section data-role="kline-chart-stub">
        <div data-role="kline-current-period">{{ currentPeriod }}</div>
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
  it('passes the active period to the chart and preserves chart/news highlighting linkage', async () => {
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
          range: '1y',
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
        researchBrief: {
          symbol: 'AAPL',
          market: 'us',
          generated_at: '2026-03-30T11:30:00Z',
          window_days: 14,
          top_action_level: 'act_now',
          has_unexplained_price_move: false,
          drivers: [],
        },
        currentPeriod: '1D',
        klineLoading: false,
        klineError: null,
      },
    });

    expect(wrapper.get('[data-role="trading-desk-price-strip"]').text()).toContain('200.10');
    expect(wrapper.get('[data-role="terminal-quote-matrix"]').text()).toContain('开盘');
    expect(wrapper.get('[data-role="terminal-quote-matrix"]').text()).toContain('昨收');
    expect(wrapper.get('[data-role="terminal-quote-matrix"]').text()).toContain('成交量');
    expect(wrapper.get('[data-role="trading-desk-summary"]').text()).toContain('更新时间');

    expect(wrapper.find('[data-role="watchlist-settings-trigger"]').exists()).toBe(false);
    expect(wrapper.get('[data-role="kline-current-period"]').text()).toBe('1D');
    expect(wrapper.get('[data-role="research-brief-panel-stub"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="research-brief-symbol"]').text()).toBe('AAPL');

    await wrapper.get('[data-role="kline-event-chip-2026-03-19"]').trigger('click');
    expect(wrapper.get('[data-role="trading-desk-news-item-101"]').attributes('data-highlighted')).toBe('true');

    await wrapper.get('[data-role="trading-desk-news-item-101"]').trigger('click');
    expect(wrapper.get('[data-role="kline-highlighted-time"]').text()).toBe('2026-03-19');
  });

  it('shows Chinese loading copy while kline data is refreshing', () => {
    const wrapper = mount(StockDetailPanel, {
      props: {
        quote: null,
        klineData: null,
        detailNews: [],
        researchBrief: null,
        currentPeriod: '1Y',
        klineLoading: true,
        klineError: null,
      },
    });

    expect(wrapper.get('[data-role="trading-desk-summary"]').text()).toContain('正在加载最新K线图');
  });
});
