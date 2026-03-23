import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { NewsDetail, NewsItem } from '../types/api';
import NewsFeedView from './NewsFeedView.vue';

const mockPush = vi.fn();

const items: NewsItem[] = [
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
];

const detailMap: Record<number, NewsDetail> = {
  1: {
    ...items[0],
    sentiment_score: null,
    article: null,
    mentions: [],
    topic: {
      id: 1,
      topic_title: 'AI Infra',
      importance_score: 0.93,
      last_seen_at: '2026-03-18T08:00:00Z',
    },
  },
  2: {
    ...items[1],
    sentiment_score: null,
    article: null,
    mentions: [],
    topic: {
      id: 2,
      topic_title: 'Semiconductor',
      importance_score: 0.82,
      last_seen_at: '2026-03-18T07:00:00Z',
    },
  },
};

const newsStore = {
  feedItems: items,
  detailMap,
  feedLoading: false,
  feedStale: false,
  usingMock: false,
  loadFeedNews: vi.fn(async () => undefined),
  loadDetail: vi.fn(async () => undefined),
};

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock('../stores/newsStore', () => ({
  useNewsStore: () => newsStore,
}));

describe('NewsFeedView', () => {
  beforeEach(() => {
    mockPush.mockReset();
    newsStore.loadFeedNews.mockClear();
    newsStore.loadDetail.mockClear();
  });

  it('renders a unified list in original order without Primary Signal', () => {
    const wrapper = mount(NewsFeedView);

    expect(wrapper.text()).toContain('Signal Desk');
    expect(wrapper.text()).toContain('Control Station');
    expect(wrapper.find('[data-role="filter-bar"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="filter-bar"]').classes()).toContain('rounded-[16px]');
    expect(wrapper.find('[data-role="news-feed-shell"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="news-stream-shell"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Primary Signal');

    const titles = wrapper.findAll('[data-role="news-card-title"]').map((node) => node.text());
    expect(titles).toEqual([
      'NVIDIA rallies as AI capex estimates move higher',
      'TSMC supply chain remains in focus',
    ]);
  });

  it('loads the feed slot instead of the shared list api', () => {
    mount(NewsFeedView);

    expect(newsStore.loadFeedNews).not.toHaveBeenCalledWith({ sentiment_label: 'positive', limit: 300 });
  });

  it('routes feed cards to the news detail page on click', async () => {
    const wrapper = mount(NewsFeedView);

    await wrapper.get('[data-role="news-card-shell"]').trigger('click');

    expect(mockPush).toHaveBeenCalledWith({ name: 'news-detail', params: { id: 1 } });
  });
});
