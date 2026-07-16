import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { NewsFeedTopic } from '../../types/api';
import TopicChipsRow from './TopicChipsRow.vue';

function makeTopic(overrides: Partial<NewsFeedTopic> = {}): NewsFeedTopic {
  return {
    id: 7,
    topic_title: 'AI 芯片',
    keywords: ['ai'],
    market: 'us',
    sentiment_label: 'positive',
    importance_score: 0.6,
    news_count: 12,
    last_seen_at: '2026-07-15T00:00:00Z',
    related_symbols: [],
    ...overrides,
  };
}

describe('TopicChipsRow', () => {
  it('渲染主题 chip 并透传点击', async () => {
    const wrapper = mount(TopicChipsRow, { props: { topics: [makeTopic()] } });
    const chip = wrapper.get('[data-role="topic-chip"]');
    expect(chip.text()).toContain('AI 芯片');
    expect(chip.text()).toContain('(12)');
    await chip.trigger('click');
    expect(wrapper.emitted('open-topic')).toEqual([[7]]);
  });

  it('空列表显示占位文案', () => {
    const wrapper = mount(TopicChipsRow, { props: { topics: [] } });
    expect(wrapper.get('[data-role="topic-chips-row"]').text()).toContain('暂无主题');
  });
});
