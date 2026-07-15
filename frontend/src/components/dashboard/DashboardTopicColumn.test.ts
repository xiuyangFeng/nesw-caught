import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import DashboardTopicColumn from './DashboardTopicColumn.vue';

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe('DashboardTopicColumn', () => {
  it('renders topics inside the topic column section card', () => {
    const wrapper = mount(DashboardTopicColumn, {
      props: {
        topics: [
          {
            id: 11,
            topic_title: 'AI 基建链走强',
            topic_summary: '算力、服务器与半导体链条同步升温。',
            keywords: [],
            sentiment_label: 'positive',
            related_symbols: ['NVDA'],
            news_count: 6,
            market: 'us',
            last_seen_at: '2026-03-18T09:00:00Z',
          },
        ] as any,
        loading: false,
      },
    });

    expect(wrapper.find('[data-role="dashboard-column-topics"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="dashboard-column-scroller"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('AI 基建链走强');
  });
});
