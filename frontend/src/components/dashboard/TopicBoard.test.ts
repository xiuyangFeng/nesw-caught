import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import TopicBoard from './TopicBoard.vue';

const push = vi.fn();

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push,
  }),
}));

describe('TopicBoard', () => {
  it('renders topic entries as terminal surface cards', () => {
    const wrapper = mount(TopicBoard, {
      props: {
        topics: [
          {
            id: 7,
            topic_title: 'China internet AI monetization',
            topic_summary: 'Platform companies are extending enterprise AI and cloud monetization narratives.',
            market: 'hk',
            sentiment_label: 'positive',
            importance_score: 0.88,
            news_count: 3,
            related_symbols: ['0700.HK'],
            last_seen_at: '2026-03-18T04:00:00Z',
          },
        ],
      },
    });

    expect(wrapper.find('[data-surface="terminal-card"]').exists()).toBe(true);
  });

  it('keeps a stable topic meta anchor and routes on click', async () => {
    const wrapper = mount(TopicBoard, {
      props: {
        topics: [
          {
            id: 7,
            topic_title: 'China internet AI monetization',
            topic_summary: 'Platform companies are extending enterprise AI and cloud monetization narratives.',
            market: 'hk',
            sentiment_label: 'positive',
            importance_score: 0.88,
            news_count: 3,
            related_symbols: ['0700.HK'],
            last_seen_at: '2026-03-18T04:00:00Z',
          },
        ],
      },
    });

    expect(wrapper.find('[data-role="topic-meta"]').exists()).toBe(true);

    await wrapper.find('[data-surface="terminal-card"]').trigger('click');

    expect(push).toHaveBeenCalledWith({ name: 'topic-detail', params: { id: 7 } });
  });
});
