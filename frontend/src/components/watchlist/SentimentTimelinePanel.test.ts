import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { HttpError } from '../../api/http';
import type { SentimentTimelineResponse } from '../../types/api';
import SentimentTimelinePanel from './SentimentTimelinePanel.vue';

const { getSentimentTimeline } = vi.hoisted(() => ({
  getSentimentTimeline: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  apiClient: {
    getSentimentTimeline,
  },
}));

const bearishTimeline: SentimentTimelineResponse = {
  symbol: 'AAPL',
  days: 30,
  points: [
    {
      date: '2026-07-27',
      avg_score: 0.34,
      news_count: 5,
      positive_count: 3,
      negative_count: 1,
      neutral_count: 1,
      top_news: [
        { id: 1, title: '苹果供应链排产超预期', sentiment_label: 'positive', sentiment_score: 0.4 },
        { id: 2, title: '分析师上调苹果目标价', sentiment_label: 'positive', sentiment_score: 0.3 },
      ],
    },
    {
      date: '2026-07-29',
      avg_score: -0.1,
      news_count: 2,
      positive_count: 0,
      negative_count: 1,
      neutral_count: 1,
      top_news: [{ id: 3, title: '短期获利了结压力', sentiment_label: 'negative', sentiment_score: -0.2 }],
    },
  ],
  divergence: {
    status: 'bearish_divergence',
    window_days: 7,
    sentiment_avg: 0.34,
    news_count: 18,
    price_change_percent: -3.8,
    detected_at: '2026-08-02T01:30:00Z',
  },
};

const bullishTimeline: SentimentTimelineResponse = {
  ...bearishTimeline,
  symbol: '0700.HK',
  divergence: {
    status: 'bullish_divergence',
    window_days: 7,
    sentiment_avg: -0.24,
    news_count: 10,
    price_change_percent: 4.1,
    detected_at: '2026-08-02T01:45:00Z',
  },
};

const noDivergenceTimeline: SentimentTimelineResponse = {
  ...bearishTimeline,
  symbol: 'NVDA',
  divergence: null,
};

const emptyTimeline: SentimentTimelineResponse = {
  symbol: 'ZZZZ',
  days: 30,
  points: [],
  divergence: null,
};

describe('SentimentTimelinePanel', () => {
  beforeEach(() => {
    getSentimentTimeline.mockReset();
  });

  it('fetches the timeline for the given symbol on mount', async () => {
    getSentimentTimeline.mockResolvedValue({ data: noDivergenceTimeline, degraded: false });

    mount(SentimentTimelinePanel, { props: { symbol: 'NVDA' } });
    await flushPromises();

    expect(getSentimentTimeline).toHaveBeenCalledWith('NVDA', 30);
  });

  it('renders a bearish divergence badge with the expected wording', async () => {
    getSentimentTimeline.mockResolvedValue({ data: bearishTimeline, degraded: false });

    const wrapper = mount(SentimentTimelinePanel, { props: { symbol: 'AAPL' } });
    await flushPromises();

    const badge = wrapper.find('[data-role="sentiment-divergence-badge"]');
    expect(badge.exists()).toBe(true);
    expect(badge.text()).toContain('情绪-价格背离：情绪偏多但价格走弱');
    expect(wrapper.find('[data-role="sentiment-timeline-chart"]').exists()).toBe(true);
    expect(wrapper.findAll('[data-role="sentiment-timeline-bar"]')).toHaveLength(2);
  });

  it('renders a bullish divergence badge with the reversed wording', async () => {
    getSentimentTimeline.mockResolvedValue({ data: bullishTimeline, degraded: false });

    const wrapper = mount(SentimentTimelinePanel, { props: { symbol: '0700.HK' } });
    await flushPromises();

    const badge = wrapper.find('[data-role="sentiment-divergence-badge"]');
    expect(badge.exists()).toBe(true);
    expect(badge.text()).toContain('情绪-价格背离：情绪偏空但价格走强');
  });

  it('hides the badge when there is no divergence', async () => {
    getSentimentTimeline.mockResolvedValue({ data: noDivergenceTimeline, degraded: false });

    const wrapper = mount(SentimentTimelinePanel, { props: { symbol: 'NVDA' } });
    await flushPromises();

    expect(wrapper.find('[data-role="sentiment-divergence-badge"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="sentiment-timeline-chart"]').exists()).toBe(true);
  });

  it('shows the empty state when there are no points', async () => {
    getSentimentTimeline.mockResolvedValue({ data: emptyTimeline, degraded: false });

    const wrapper = mount(SentimentTimelinePanel, { props: { symbol: 'ZZZZ' } });
    await flushPromises();

    expect(wrapper.find('[data-role="sentiment-timeline-empty"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="sentiment-timeline-chart"]').exists()).toBe(false);
  });

  it('shows an error state when the request fails', async () => {
    getSentimentTimeline.mockRejectedValue(new HttpError('时间线服务不可用', 503));

    const wrapper = mount(SentimentTimelinePanel, { props: { symbol: 'AAPL' } });
    await flushPromises();

    expect(wrapper.find('[data-role="sentiment-timeline-error"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('时间线服务不可用');
  });

  it('reloads the timeline when the symbol prop changes', async () => {
    getSentimentTimeline.mockResolvedValue({ data: bearishTimeline, degraded: false });

    const wrapper = mount(SentimentTimelinePanel, { props: { symbol: 'AAPL' } });
    await flushPromises();
    getSentimentTimeline.mockClear();
    getSentimentTimeline.mockResolvedValue({ data: bullishTimeline, degraded: false });

    await wrapper.setProps({ symbol: '0700.HK' });
    await flushPromises();

    expect(getSentimentTimeline).toHaveBeenCalledWith('0700.HK', 30);
    expect(wrapper.find('[data-role="sentiment-divergence-badge"]').text()).toContain('情绪偏空但价格走强');
  });
});
