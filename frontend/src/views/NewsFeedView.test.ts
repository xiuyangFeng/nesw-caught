import { flushPromises, mount } from '@vue/test-utils';
import { reactive, nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { NewsDetail, NewsItem } from '../types/api';
import { resetReadNewsForTest } from '../utils/readNews';
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

const feedLayout = {
  events: [
    {
      event_key: 'topic-1',
      event_title: 'AI Chip Launch',
      event_summary: 'NVIDIA 新一轮 AI 芯片发布带动供应链关注度上升。',
      event_type: 'product',
      market: 'us',
      sentiment_label: 'positive',
      importance_score: 0.93,
      last_seen_at: '2026-03-18T08:00:00Z',
      primary_symbol: 'NVDA',
      related_symbols: ['NVDA', 'SMCI'],
      watchlist_hits: ['NVIDIA', 'Supermicro'],
      source_count: 2,
      news_count: 2,
      news_items: items,
    },
  ],
  topics: [
    {
      id: 1,
      topic_title: 'AI Infra',
      topic_summary: '算力与供应链持续走强。',
      keywords: ['ai', 'infra'],
      market: 'us',
      sentiment_label: 'positive',
      importance_score: 0.93,
      news_count: 2,
      last_seen_at: '2026-03-18T08:00:00Z',
      related_symbols: ['NVDA', 'SMCI'],
    },
  ],
  stream: items,
};

const newsStore = reactive({
  feedLayout,
  feedLayoutDegraded: false,
  feedItems: items,
  detailMap,
  detailLoading: false,
  analysisMap: {} as Record<number, any>,
  analysisLoadingMap: {} as Record<number, boolean>,
  analysisErrorMap: {} as Record<number, string | null>,
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
  feedNextCursor: null,
  feedHasMore: false,
  feedLoadingMore: false,
  loadFeedNews: vi.fn(async () => undefined),
  loadFeedLayout: vi.fn(async () => undefined),
  loadMoreFeedNews: vi.fn(async () => false),
  loadDetail: vi.fn(async (_id: number): Promise<void> => undefined),
  loadAnalysis: vi.fn(async (_id: number): Promise<void> => undefined),
});

vi.mock('vue-router', () => ({
  RouterLink: {
    name: 'RouterLink',
    props: ['to'],
    template: '<a :href="typeof to === \'string\' ? to : to?.path"><slot /></a>',
  },
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

vi.mock('../stores/llmStore', () => ({
  useLlmStore: () => ({
    config: null,
    loadConfig: vi.fn(),
  }),
}));

describe('NewsFeedView', () => {
  beforeEach(() => {
    class MockIntersectionObserver {
      observe = vi.fn();
      disconnect = vi.fn();
      unobserve = vi.fn();
      constructor(public callback: IntersectionObserverCallback) {}
    }
    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver as unknown as typeof IntersectionObserver);

    resetReadNewsForTest();
    mockPush.mockReset();
    connectionStore.state = 'live';
    newsStore.loadFeedNews.mockClear();
    newsStore.loadFeedLayout.mockClear();
    newsStore.loadDetail.mockClear();
    newsStore.loadAnalysis.mockClear();
    newsStore.feedLayoutDegraded = false;
    newsStore.feedItems = items;
    newsStore.feedLayout = feedLayout;
    newsStore.detailMap = detailMap;
    newsStore.analysisMap = {};
    newsStore.analysisLoadingMap = {};
    newsStore.analysisErrorMap = {};
  });

  it('frames the page as compact latest-event discovery instead of signal desk copy', () => {
    const wrapper = mount(NewsFeedView);

    expect(wrapper.findAll('h1').map((node) => node.text())).toEqual(['Latest Events']);
    expect(wrapper.text()).not.toContain('Signal Desk');
    expect(wrapper.text()).not.toContain('News Feed');
    expect(wrapper.findAll('h2').map((node) => node.text())).not.toContain('Latest Events');
    expect(wrapper.text()).toContain('Raw Stream');
    expect(wrapper.text()).not.toContain('先扫最新事件，再看主题簇和原始新闻流作为证据层。');
    expect(wrapper.find('[data-role="filter-bar"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="news-feed-toolbar"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="news-feed-shell"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="feed-compact-header"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="event-capsule-strip"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="topic-chips-row"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="event-radar-shell"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="topic-watch-shell"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="news-stream-shell"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('持仓 2');
    expect(wrapper.text()).toContain('AI Chip Launch');
    expect(wrapper.text()).toContain('AI Infra');

    const titles = wrapper.findAll('[data-role="news-card-title"]').map((node) => node.text());
    expect(titles).toEqual([
      'NVIDIA rallies as AI capex estimates move higher',
      'TSMC supply chain remains in focus',
    ]);
  });

  it('loads the event layout and the raw stream in parallel', () => {
    mount(NewsFeedView);

    expect(newsStore.loadFeedLayout).toHaveBeenCalled();
    expect(newsStore.loadFeedNews).toHaveBeenCalled();
  });

  it('passes an AbortSignal when reloading the feed after filter changes', async () => {
    vi.useFakeTimers();
    const wrapper = mount(NewsFeedView);
    await flushPromises();

    newsStore.loadFeedNews.mockClear();
    newsStore.loadFeedLayout.mockClear();

    await wrapper.find('input[type="search"]').setValue('nvidia');
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();

    expect(newsStore.loadFeedNews).toHaveBeenCalledTimes(1);
    const [query, signal] = newsStore.loadFeedNews.mock.calls[0] as unknown as [
      { q?: string },
      AbortSignal,
    ];
    expect(query.q).toBe('nvidia');
    expect(signal).toBeInstanceOf(AbortSignal);
    expect(signal.aborted).toBe(false);
    // 搜索不切换市场时不重拉 layout
    expect(newsStore.loadFeedLayout).not.toHaveBeenCalled();

    // 再次输入会 abort 上一轮的 signal
    const previousSignal = signal;
    await wrapper.find('input[type="search"]').setValue('nvidia tsmc');
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();

    expect(previousSignal.aborted).toBe(true);
    expect(newsStore.loadFeedNews).toHaveBeenCalledTimes(2);

    wrapper.unmount();
    vi.useRealTimers();
  });

  it('routes event cards to the event detail page on open-event', async () => {
    const wrapper = mount(NewsFeedView);

    await wrapper.getComponent({ name: 'EventCapsuleStrip' }).vm.$emit('open-event', 'topic-1');

    expect(mockPush).toHaveBeenCalledWith({ name: 'event-detail', params: { eventKey: 'topic-1' } });
  });

  it('routes topic chips to the topic detail page on open-topic', async () => {
    const wrapper = mount(NewsFeedView);

    await wrapper.getComponent({ name: 'TopicChipsRow' }).vm.$emit('open-topic', 1);

    expect(mockPush).toHaveBeenCalledWith({ name: 'topic-detail', params: { id: 1 } });
  });

  it('opens the detail drawer instead of routing to the news-detail page when a card is clicked', async () => {
    const wrapper = mount(NewsFeedView);

    await wrapper.get('[data-role="news-card-shell"]').trigger('click');

    expect(mockPush).not.toHaveBeenCalledWith({ name: 'news-detail', params: { id: expect.anything() } });
    const drawer = wrapper.findComponent({ name: 'NewsDetailDrawer' });
    expect(drawer.props('newsId')).not.toBeNull();
    expect(drawer.props('visible')).toBe(true);
  });

  it('marks a news card as read after it has been opened via the drawer', async () => {
    const wrapper = mount(NewsFeedView);

    const card = wrapper.get('[data-role="news-card-shell"]');
    await card.trigger('click');

    expect(wrapper.get('[data-role="news-card-shell"]').classes()).toContain('news-card--read');
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

  it('keeps rendering the raw stream when there are no derived events', () => {
    newsStore.feedLayout = {
      events: [],
      topics: [],
      stream: items,
    };

    const wrapper = mount(NewsFeedView);

    expect(wrapper.text()).toContain('暂无聚合事件');
    expect(wrapper.find('[data-role="news-stream-shell"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('NVIDIA rallies as AI capex estimates move higher');

    newsStore.feedLayout = feedLayout;
  });

  it('keeps derived sections visible when stream filters to empty', () => {
    newsStore.feedLayout = {
      events: feedLayout.events,
      topics: feedLayout.topics,
      stream: [],
    };
    newsStore.feedItems = [];

    const wrapper = mount(NewsFeedView);

    expect(wrapper.text()).toContain('AI Chip Launch');
    expect(wrapper.text()).toContain('AI Infra');
    expect(wrapper.find('[data-role="feed-compact-header"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="event-capsule-strip"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="topic-chips-row"]').exists()).toBe(true);

    newsStore.feedLayout = feedLayout;
    newsStore.feedItems = items;
  });

  it('applies active feed filters to topic watch as well', async () => {
    const wrapper = mount(NewsFeedView);

    await wrapper.findAll('select')[1].setValue('negative');

    expect(wrapper.text()).not.toContain('AI Infra');
  });

  it('folds low-priority stream entries behind a toggle and expands them on click', async () => {
    const foldableItems: NewsItem[] = Array.from({ length: 16 }, (_, index) => ({
      id: index + 1,
      title: `Fold story ${index + 1}`,
      summary: `Summary ${index + 1}`,
      source_name: 'Reuters',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'neutral',
      published_at: `2026-03-18T${String(index).padStart(2, '0')}:00:00Z`,
      fetched_at: `2026-03-18T${String(index).padStart(2, '0')}:02:00Z`,
      editorial_score: 1 - index * 0.05,
    }));

    newsStore.feedItems = foldableItems;
    newsStore.feedLayout = {
      events: [],
      topics: [],
      stream: foldableItems,
    };
    newsStore.detailMap = {};

    const wrapper = mount(NewsFeedView);
    await nextTick();

    const toggle = wrapper.get('[data-role="news-fold-toggle"]');
    expect(toggle.text()).toContain('已折叠');

    const beforeCount = wrapper.findAll('[data-role="news-card-shell"]').length;
    await toggle.trigger('click');
    const afterCount = wrapper.findAll('[data-role="news-card-shell"]').length;

    expect(afterCount).toBeGreaterThan(beforeCount);
    expect(wrapper.get('[data-role="news-fold-toggle"]').text()).toContain('收起');

    newsStore.feedItems = items;
    newsStore.feedLayout = feedLayout;
    newsStore.detailMap = detailMap;
  });

  it('shows the keyboard shortcut hint below the raw stream', () => {
    const wrapper = mount(NewsFeedView);

    expect(wrapper.find('[data-role="feed-kbd-hint"]').exists()).toBe(true);
  });

  it('falls back to the raw feed when the layout response is degraded', () => {
    newsStore.feedLayoutDegraded = true;
    newsStore.feedLayout = {
      ...feedLayout,
      stream: [
        {
          id: 99,
          title: 'Layout fallback should not win',
          summary: 'Degraded layout stream entry',
          source_name: 'Mock Source',
          canonical_url: null,
          market: 'us',
          sentiment_label: 'neutral',
          published_at: '2026-03-18T09:00:00Z',
          fetched_at: '2026-03-18T09:01:00Z',
        },
      ],
    };
    newsStore.feedItems = items;

    const wrapper = mount(NewsFeedView);

    expect(wrapper.text()).toContain('NVIDIA rallies as AI capex estimates move higher');
    expect(wrapper.text()).not.toContain('Layout fallback should not win');

    newsStore.feedLayoutDegraded = false;
    newsStore.feedLayout = feedLayout;
    newsStore.feedItems = items;
  });

  it('does not let degraded layout scores reorder the raw stream', () => {
    newsStore.feedLayoutDegraded = true;
    newsStore.feedItems = [
      {
        id: 10,
        title: 'Raw first story',
        summary: 'raw 1',
        source_name: 'Reuters',
        canonical_url: null,
        market: 'us',
        sentiment_label: 'neutral',
        published_at: '2026-03-18T10:00:00Z',
        fetched_at: '2026-03-18T10:01:00Z',
      },
      {
        id: 11,
        title: 'Raw second story',
        summary: 'raw 2',
        source_name: 'Bloomberg',
        canonical_url: null,
        market: 'us',
        sentiment_label: 'neutral',
        published_at: '2026-03-18T09:00:00Z',
        fetched_at: '2026-03-18T09:01:00Z',
      },
    ];
    newsStore.feedLayout = {
      events: [],
      topics: [],
      stream: [
        { ...newsStore.feedItems[1], editorial_score: 0.99 },
        { ...newsStore.feedItems[0], editorial_score: 0.01 },
      ],
    };
    newsStore.detailMap = {};

    const wrapper = mount(NewsFeedView);
    const titles = wrapper.findAll('[data-role="news-card-title"]').map((node) => node.text());

    expect(titles).toEqual(['Raw first story', 'Raw second story']);
  });

  it('hydrates details for stories promoted by ranked stream order instead of raw feed order', async () => {
    const promotedItems: NewsItem[] = Array.from({ length: 9 }, (_, index) => ({
      id: index + 1,
      title: `Story ${index + 1}`,
      summary: `Summary ${index + 1}`,
      source_name: 'Reuters',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'neutral',
      published_at: `2026-03-18T0${Math.min(index, 8)}:00:00Z`,
      fetched_at: `2026-03-18T0${Math.min(index, 8)}:02:00Z`,
    }));

    newsStore.feedItems = promotedItems;
    newsStore.feedLayout = {
      events: [],
      topics: [],
      stream: promotedItems.map((item) => ({
        ...item,
        editorial_score: item.id === 9 ? 0.99 : 0.1,
      })),
    };
    newsStore.detailMap = {};

    mount(NewsFeedView);
    await Promise.resolve();
    await Promise.resolve();

    expect(newsStore.loadDetail).toHaveBeenCalledWith(9);

    newsStore.feedItems = items;
    newsStore.feedLayout = feedLayout;
    newsStore.detailMap = detailMap;
  });

  it('hydrates newly promoted ranked stories after earlier detail loads settle', async () => {
    const promotedItems: NewsItem[] = Array.from({ length: 9 }, (_, index) => ({
      id: index + 1,
      title: `Story ${index + 1}`,
      summary: `Summary ${index + 1}`,
      source_name: 'Reuters',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'neutral',
      published_at: `2026-03-18T0${Math.min(index, 8)}:00:00Z`,
      fetched_at: `2026-03-18T0${Math.min(index, 8)}:02:00Z`,
      editorial_score: index === 8 ? 0.4 : 0.5,
    }));

    newsStore.feedItems = promotedItems;
    newsStore.feedLayout = {
      events: [],
      topics: [],
      stream: promotedItems,
    };
    newsStore.detailMap = {};

    newsStore.loadDetail.mockImplementation(async (id: number) => {
      newsStore.detailMap = {
        ...newsStore.detailMap,
        [id]: {
          ...promotedItems[id - 1],
          sentiment_score: null,
          article: null,
          mentions: [],
          topic: {
            id,
            topic_title: `Topic ${id}`,
            importance_score: 0,
            last_seen_at: promotedItems[id - 1].published_at ?? promotedItems[id - 1].fetched_at,
          },
        },
      };
      if (id === 8) {
        newsStore.feedLayout = {
          ...newsStore.feedLayout,
          stream: promotedItems.map((item) => ({
            ...item,
            editorial_score: item.id === 9 ? 0.99 : 0.01,
          })),
        };
      }
    });

    mount(NewsFeedView);
    await nextTick();
    await Promise.resolve();
    await nextTick();
    await Promise.resolve();

    expect(newsStore.loadDetail).toHaveBeenCalledWith(9);

    newsStore.loadDetail.mockImplementation(async () => undefined);
    newsStore.feedItems = items;
    newsStore.feedLayout = feedLayout;
    newsStore.detailMap = detailMap;
  });

  it('does not keep stale virtual visible ids when the stream stops using virtualization', async () => {
    // 50 条:折叠段 P70 之后约 15 条被折叠,可见段仍有 35 条 > VIRTUAL_LIST_THRESHOLD(30),
    // 保证折叠不会意外把这条用例的初始态从「虚拟滚动」降级为「非虚拟」。
    const manyItems: NewsItem[] = Array.from({ length: 50 }, (_, index) => ({
      id: index + 1,
      title: `Story ${index + 1}`,
      summary: `Summary ${index + 1}`,
      source_name: 'Reuters',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-03-18T10:00:00Z',
      fetched_at: '2026-03-18T10:01:00Z',
      editorial_score: 0.5,
    }));

    newsStore.feedItems = manyItems;
    newsStore.feedLayout = {
      events: [],
      topics: [],
      stream: manyItems,
    };
    newsStore.detailMap = {};

    const wrapper = mount(NewsFeedView);
    await nextTick();

    const virtualList = wrapper.findComponent({ name: 'NewsVirtualList' });
    expect(virtualList.exists()).toBe(true);
    await virtualList.vm.$emit('visible-ids', [3, 4, 5]);
    // feedItems 同步 watcher 已改为 flush:'post',hydra 链路内部也有 nextTick 排队,
    // 这里用 flushPromises 让在途的 detail 补水完全结算后再清零断言基线。
    await flushPromises();
    await nextTick();
    newsStore.loadDetail.mockClear();

    newsStore.feedItems = manyItems.slice(0, 2);
    newsStore.feedLayout = {
      events: [],
      topics: [],
      stream: manyItems.slice(0, 2),
    };
    newsStore.detailMap = {
      1: {
        ...manyItems[0],
        sentiment_score: null,
        article: null,
        mentions: [],
        topic: null,
      },
      2: {
        ...manyItems[1],
        sentiment_score: null,
        article: null,
        mentions: [],
        topic: null,
      },
    };
    newsStore.loadDetail.mockClear();

    await nextTick();
    await Promise.resolve();

    expect(wrapper.findComponent({ name: 'NewsVirtualList' }).exists()).toBe(false);
    expect(newsStore.loadDetail).not.toHaveBeenCalled();

    newsStore.feedItems = items;
    newsStore.feedLayout = feedLayout;
    newsStore.detailMap = detailMap;
  });
});
