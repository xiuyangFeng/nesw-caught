import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { NewsFeedEventCard } from '../../types/api';
import EventCapsuleStrip from './EventCapsuleStrip.vue';

function makeEvent(overrides: Partial<NewsFeedEventCard> = {}): NewsFeedEventCard {
  return {
    event_key: 'topic-1',
    event_title: '英伟达上调指引',
    event_type: 'earnings',
    market: 'us',
    sentiment_label: 'positive',
    importance_score: 0.8,
    primary_symbol: 'NVDA',
    related_symbols: ['NVDA'],
    watchlist_hits: ['NVDA 英伟达'],
    source_count: 3,
    news_count: 5,
    news_items: [],
    ...overrides,
  };
}

describe('EventCapsuleStrip', () => {
  it('渲染事件胶囊并透传点击', async () => {
    const wrapper = mount(EventCapsuleStrip, { props: { events: [makeEvent()] } });
    const capsule = wrapper.get('[data-role="event-capsule"]');
    expect(capsule.text()).toContain('英伟达上调指引');
    expect(capsule.text()).toContain('US');
    await capsule.trigger('click');
    expect(wrapper.emitted('open-event')).toEqual([['topic-1']]);
  });

  it('空列表显示占位文案', () => {
    const wrapper = mount(EventCapsuleStrip, { props: { events: [] } });
    expect(wrapper.get('[data-role="event-capsule-strip"]').text()).toContain('暂无聚合事件');
  });

  it('命中持仓时显示计数徽标', () => {
    const wrapper = mount(EventCapsuleStrip, { props: { events: [makeEvent()] } });
    expect(wrapper.text()).toContain('持仓 1');
  });
});
