import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { NewsFeedEventCard } from '../../types/api';
import EventFeedCard from './EventFeedCard.vue';

const event: NewsFeedEventCard = {
  event_key: 'ai-chip-launch',
  event_title: 'AI Chip Launch',
  event_summary: 'NVIDIA 新一轮 AI 芯片发布带动供应链关注度上升。',
  event_type: 'product',
  market: 'us',
  sentiment_label: 'positive',
  importance_score: 0.93,
  last_seen_at: '2026-03-18T08:00:00Z',
  primary_symbol: 'NVDA',
  related_symbols: ['NVDA', 'SMCI'],
  source_count: 2,
  news_count: 2,
  news_items: [
    {
      id: 1,
      title: 'NVIDIA rallies as AI capex estimates move higher',
      summary: 'Lead story summary.',
      source_name: 'Bloomberg',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'positive',
      published_at: '2026-03-18T08:00:00Z',
      fetched_at: '2026-03-18T08:03:00Z',
    },
    {
      id: 2,
      title: 'TSMC supply chain remains in focus',
      summary: 'Supporting summary.',
      source_name: 'Reuters',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-03-18T07:00:00Z',
      fetched_at: '2026-03-18T07:05:00Z',
    },
  ],
};

describe('EventFeedCard', () => {
  it('emits open-event from the primary shell and keeps evidence pills on open-story only', async () => {
    const wrapper = mount(EventFeedCard, {
      props: { event },
    });

    expect(wrapper.classes()).toContain('event-feed-card--compact');
    expect(wrapper.find('[data-role="event-card-title"]').text()).toBe('AI Chip Launch');
    expect(wrapper.get('[data-role="event-card-primary"]').attributes('type')).toBe('button');
    expect(wrapper.text()).toContain('product');
    expect(wrapper.text()).toContain('NVDA');
    expect(wrapper.text()).toContain('SMCI');

    const evidenceButtons = wrapper.findAll('[data-role="event-card-story"]');
    expect(evidenceButtons).toHaveLength(2);

    await wrapper.get('[data-role="event-card-primary"]').trigger('click');
    expect(wrapper.emitted('open-event')).toEqual([['ai-chip-launch']]);
    expect(wrapper.emitted('open-story')).toBeUndefined();

    await evidenceButtons[1].trigger('click');
    expect(wrapper.emitted('open-story')).toEqual([[2]]);
  });
});
