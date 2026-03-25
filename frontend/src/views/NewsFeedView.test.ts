import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { NewsDetail, NewsItem } from '../types/api';
import NewsFeedView from './NewsFeedView.vue';

const mockPush = vi.fn();
const connectionStore = {
  state: 'live',
};

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
  newsRuntimeStatus: {
    feed_status: 'delayed',
    last_refresh_finished_at: '2026-03-25T02:40:00Z',
    last_news_created_at: '2026-03-25T02:39:40Z',
    last_incremental_event_at: '2026-03-25T02:39:55Z',
    degraded_market_count: 1,
    markets: [],
    sources: [
      {
        source_name: 'Bloomberg',
        market: 'us',
        tier: 'primary',
        status: 'degraded',
        last_attempt_at: '2026-03-25T02:39:20Z',
        last_success_at: '2026-03-25T02:39:30Z',
        consecutive_failures: 2,
        avg_fetch_latency_ms: 320,
        latest_news_published_at: '2026-03-25T02:35:00Z',
        latest_news_fetched_at: '2026-03-25T02:39:30Z',
        last_error: 'timeout',
      },
    ],
  },
  sourceHealth: [
    {
      source_name: 'Bloomberg',
      market: 'us',
      tier: 'primary',
      status: 'degraded',
      last_attempt_at: '2026-03-25T02:39:20Z',
      last_success_at: '2026-03-25T02:39:30Z',
      consecutive_failures: 2,
      avg_fetch_latency_ms: 320,
      latest_news_published_at: '2026-03-25T02:35:00Z',
      latest_news_fetched_at: '2026-03-25T02:39:30Z',
      last_error: 'timeout',
    },
  ],
  lastIncrementalAt: '2026-03-25T02:39:55Z',
  loadFeedNews: vi.fn(async () => undefined),
  loadDetail: vi.fn(async () => undefined),
};

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock('../stores/connectionStore', () => ({
  useConnectionStore: () => connectionStore,
}));

vi.mock('../stores/newsStore', () => ({
  useNewsStore: () => newsStore,
}));

describe('NewsFeedView', () => {
  beforeEach(() => {
    mockPush.mockReset();
    connectionStore.state = 'live';
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

  it('renders delayed/degraded/live status copy in the feed header', () => {
    const wrapper = mount(NewsFeedView);

    expect(wrapper.text()).toContain('新闻更新延迟');
    expect(wrapper.text()).toContain('最近入流');
    expect(wrapper.text()).toContain('异常来源');
  });

  it('overrides runtime status copy when the sse connection is degraded', () => {
    connectionStore.state = 'offline';

    const wrapper = mount(NewsFeedView);

    expect(wrapper.text()).toContain('实时连接异常');
  });
});
