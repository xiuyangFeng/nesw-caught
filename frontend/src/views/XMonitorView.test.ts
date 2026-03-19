import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import XMonitorView from './XMonitorView.vue';

const translationState = reactive<Record<string, { status: string; translated_text: string | null; error: string | null }>>({});

const xMonitorStore = reactive({
  accounts: [
    {
      id: 1,
      handle: 'DeItaone',
      display_name: 'Delta One',
      market_focus: 'us',
      is_active: true,
      priority: 100,
      notes: 'Macro and market headlines',
    },
  ],
  posts: [
    {
      id: 1,
      account_handle: 'DeItaone',
      account_display_name: 'Delta One',
      content_text: 'NVDA suppliers remain in focus',
      canonical_url: 'https://x.com/DeItaone/status/190001',
      market: 'us',
      sentiment_label: 'unknown',
      relevance_score: null,
      posted_at: '2026-03-19T08:00:00Z',
      captured_at: '2026-03-19T08:01:00Z',
      symbols: ['NVDA'],
    },
  ],
  searchQuery: 'NVDA',
  searchResults: [
    {
      id: 0,
      account_handle: 'SawyerMerritt',
      account_display_name: 'Sawyer Merritt',
      content_text: 'NVDA demand remains strong',
      canonical_url: 'https://x.com/SawyerMerritt/status/190003',
      market: 'us',
      sentiment_label: 'unknown',
      relevance_score: null,
      posted_at: '2026-03-19T08:02:00Z',
      captured_at: '2026-03-19T08:02:00Z',
      symbols: ['NVDA'],
    },
  ],
  health: {
    enabled: true,
    configured: true,
    healthy: true,
    status: 'configured',
    provider_name: 'twitterapi.io',
    min_interval_seconds: 6,
    refresh_cooldown_hours: 3,
    last_success_at: '2026-03-19T08:05:00Z',
    last_failure_at: null,
    consecutive_failures: 0,
    total_fetches: 2,
    total_failures: 0,
    avg_latency_ms: 320,
    last_error: null,
  },
  loading: false,
  healthLoading: false,
  refreshLoading: false,
  searchLoading: false,
  usingMock: false,
  stale: false,
  lastRefresh: null,
  filters: reactive({
    account_handle: '',
    market: '',
    q: '',
  }),
  translationsByKey: translationState,
  getTranslationKey: vi.fn((post) => post.canonical_url ?? `${post.account_handle}:${post.posted_at ?? post.captured_at}:${post.content_text}`),
  bootstrap: vi.fn().mockResolvedValue(undefined),
  loadPosts: vi.fn().mockResolvedValue(undefined),
  refreshPosts: vi.fn().mockResolvedValue(undefined),
  searchPosts: vi.fn().mockResolvedValue(undefined),
  translatePost: vi.fn().mockImplementation(async (post) => {
    const key = post.canonical_url ?? `${post.account_handle}:${post.posted_at ?? post.captured_at}:${post.content_text}`;
    translationState[key] = {
      status: 'success',
      translated_text: `中文：${post.content_text}`,
      error: null,
    };
  }),
});

vi.mock('../stores/xMonitorStore', () => ({
  useXMonitorStore: () => xMonitorStore,
}));

describe('XMonitorView', () => {
  beforeEach(() => {
    xMonitorStore.bootstrap.mockClear();
    xMonitorStore.loadPosts.mockClear();
    xMonitorStore.refreshPosts.mockClear();
    xMonitorStore.searchPosts.mockClear();
    xMonitorStore.translatePost.mockClear();
    xMonitorStore.getTranslationKey.mockClear();
    xMonitorStore.searchQuery = 'NVDA';
    xMonitorStore.lastRefresh = null;
    xMonitorStore.searchResults = [
      {
        id: 0,
        account_handle: 'SawyerMerritt',
        account_display_name: 'Sawyer Merritt',
        content_text: 'NVDA demand remains strong',
        canonical_url: 'https://x.com/SawyerMerritt/status/190003',
        market: 'us',
        sentiment_label: 'unknown',
        relevance_score: null,
        posted_at: '2026-03-19T08:02:00Z',
        captured_at: '2026-03-19T08:02:00Z',
        symbols: ['NVDA'],
      },
    ];
    Object.keys(translationState).forEach((key) => {
      delete translationState[key];
    });
  });

  it('renders twitterapi.io provider messaging and keyword search results', async () => {
    const wrapper = mount(XMonitorView);

    expect(wrapper.text()).toContain('twitterapi.io');
    expect(wrapper.text()).toContain('关键词搜索');
    expect(wrapper.text()).toContain('请求节流');
    expect(wrapper.text()).toContain('6 秒/次');
    expect(wrapper.text()).toContain('账号刷新冷却');
    expect(wrapper.text()).toContain('3 小时');
    expect(wrapper.text()).toContain('当前跟踪 1 条帖子');
    expect(wrapper.text()).toContain('帖子流已同步到最新窗口');
    expect(wrapper.find('[data-role="x-monitor-layout"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="feed-summary"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="feed-summary-title"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="feed-summary-detail"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="post-feed"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="post-list-item"]').exists()).toBe(true);
    expect(wrapper.find('input[type="search"][placeholder*="关键词"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('NVDA demand remains strong');
    expect(wrapper.text()).toContain('账号监控帖子流');
    expect(wrapper.text()).toContain('翻译');
  });

  it('shows next refresh time when cooldown skip metadata exists', () => {
    xMonitorStore.lastRefresh = {
      started_at: '2026-03-19T09:00:00Z',
      finished_at: '2026-03-19T09:00:00Z',
      fetched_count: 0,
      inserted_count: 0,
      error: null,
      latency_ms: 0,
      skipped: true,
      skip_reason: 'cooldown_active',
      next_refresh_at: '2026-03-19T12:00:00Z',
    };

    const wrapper = mount(XMonitorView);

    expect(wrapper.text()).toContain('下次可刷新');
  });

  it('translates monitored posts on demand and renders the translated text', async () => {
    const wrapper = mount(XMonitorView);

    const translateButtons = wrapper.findAll('button[data-role="translate-button"]');
    await translateButtons[0].trigger('click');

    expect(xMonitorStore.translatePost).toHaveBeenCalledWith(xMonitorStore.posts[0]);
    expect(wrapper.text()).toContain('中文：NVDA suppliers remain in focus');
  });

  it('renders translation errors per post', () => {
    translationState['https://x.com/DeItaone/status/190001'] = {
      status: 'error',
      translated_text: null,
      error: 'llm provider is not configured',
    };

    const wrapper = mount(XMonitorView);

    expect(wrapper.text()).toContain('llm provider is not configured');
  });

  it('renders translation controls and translated text for search results without id collisions', async () => {
    xMonitorStore.searchResults = [
      {
        id: 0,
        account_handle: 'SawyerMerritt',
        account_display_name: 'Sawyer Merritt',
        content_text: 'Repeated translation text',
        canonical_url: null,
        market: 'us',
        sentiment_label: 'unknown',
        relevance_score: null,
        posted_at: '2026-03-19T08:02:00Z',
        captured_at: '2026-03-19T08:02:00Z',
        symbols: ['NVDA'],
      },
      {
        id: 0,
        account_handle: 'OpenClaw',
        account_display_name: 'OpenClaw',
        content_text: 'Repeated translation text',
        canonical_url: null,
        market: 'us',
        sentiment_label: 'unknown',
        relevance_score: null,
        posted_at: '2026-03-19T08:03:00Z',
        captured_at: '2026-03-19T08:03:00Z',
        symbols: [],
      },
    ];

    const wrapper = mount(XMonitorView);
    const translateButtons = wrapper.findAll('button[data-role="translate-button"]');

    await translateButtons.at(-2)?.trigger('click');
    await translateButtons.at(-1)?.trigger('click');

    expect(wrapper.text()).toContain('中文：Repeated translation text');
    expect(xMonitorStore.translatePost).toHaveBeenNthCalledWith(1, xMonitorStore.searchResults[0]);
    expect(xMonitorStore.translatePost).toHaveBeenNthCalledWith(2, xMonitorStore.searchResults[1]);
    expect(xMonitorStore.getTranslationKey).toHaveBeenCalledWith(xMonitorStore.searchResults[0]);
    expect(xMonitorStore.getTranslationKey).toHaveBeenCalledWith(xMonitorStore.searchResults[1]);
  });
});
