import { mount } from '@vue/test-utils';
import { reactive, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TopicDetailView from './TopicDetailView.vue';

const push = vi.fn();
const route = reactive({
  params: {
    id: '7',
  },
});

const topicStore = reactive({
  stale: false,
  detailLoading: false,
  detailMap: {
    7: {
      id: 7,
      topic_title: 'China internet AI monetization',
      topic_summary: 'Platform companies are extending enterprise AI and cloud monetization narratives.',
      market: 'hk',
      sentiment_label: 'positive',
      news_count: 2,
      related_symbols: ['0700.HK', '9988.HK'],
      keywords: ['AI', 'Cloud'],
      last_seen_at: '2026-03-18T04:00:00Z',
      sources: [
        {
          id: 11,
          title: 'Tencent expands enterprise AI product suite',
          summary: 'Tencent pushes deeper into enterprise AI workflows.',
          source_name: 'Reuters',
          market: 'hk',
          sentiment_label: 'positive',
          canonical_url: 'https://example.com/reuters',
          published_at: '2026-03-18T00:40:00Z',
          fetched_at: '2026-03-18T00:45:00Z',
        },
        {
          id: 12,
          title: 'Alibaba cloud margins improve',
          summary: 'Alibaba cloud monetization remains in focus.',
          source_name: 'Bloomberg',
          market: 'hk',
          sentiment_label: 'neutral',
          canonical_url: null,
          published_at: '2026-03-18T01:40:00Z',
          fetched_at: '2026-03-18T01:45:00Z',
        },
      ],
    },
  } as Record<number, any>,
  loadDetail: vi.fn(async () => undefined),
});

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({
    push,
  }),
}));

vi.mock('../stores/topicStore', () => ({
  useTopicStore: () => topicStore,
}));

describe('TopicDetailView', () => {
  beforeEach(() => {
    push.mockReset();
    topicStore.loadDetail.mockClear();
  });

  it('renders grouped source layout anchors and opens source detail', async () => {
    const wrapper = mount(TopicDetailView);

    expect(wrapper.find('[data-role="topic-detail-layout"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="topic-toolbar"]').exists()).toBe(true);
    expect(wrapper.find('[data-shell="topic-toolbar-shell"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="topic-group-list"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="topic-summary-shell"]').exists()).toBe(true);

    await wrapper.find('[data-role="topic-source-card"]').trigger('click');

    expect(push).toHaveBeenCalledWith({ name: 'news-detail', params: { id: 12 } });
  });

  it('renders timeline mode with terminal midstate cards', async () => {
    const wrapper = mount(TopicDetailView);

    await wrapper.get('button:last-of-type').trigger('click');

    expect(wrapper.find('[data-role="topic-timeline-card"]').exists()).toBe(true);
  });
});
