import { mount } from '@vue/test-utils';
import { nextTick, reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardView from './DashboardView.vue';

const mockPush = vi.fn();

const connectionStore = reactive({
  state: 'live',
  usingMock: false,
  streamError: null as string | null,
});

const newsStore = reactive({
  dashboardItems: [
    {
      id: 1,
      title: 'AI infrastructure names lead the session',
      summary: 'Lead item summary',
      source_name: 'Bloomberg',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'positive',
      published_at: '2026-03-18T08:00:00Z',
      fetched_at: '2026-03-18T08:03:00Z',
    },
  ],
  dashboardLoading: false,
  dashboardStale: false,
});

const marketStore = reactive({
  abnormalMovers: [
    {
      symbol: 'NVDA',
      market: 'us',
      display_name: 'NVIDIA',
      abnormal_reason: 'price_spike',
    },
    {
      symbol: '0700.HK',
      market: 'hk',
      display_name: 'Tencent',
      abnormal_reason: 'price_move',
    },
    {
      symbol: '9988.HK',
      market: 'hk',
      display_name: 'Alibaba',
      abnormal_reason: 'price_move',
    },
    {
      symbol: 'AAPL',
      market: 'us',
      display_name: 'Apple',
      abnormal_reason: 'volume_spike',
    },
  ],
  loading: false,
  stale: false,
});

const topicStore = reactive({
  topTopics: [
    {
      id: 11,
      topic_title: 'AI 基建链走强',
      topic_summary: '算力、服务器与半导体链条同步升温。',
      keywords: [],
      sentiment_label: 'positive',
      related_symbols: ['NVDA', 'SMCI'],
      news_count: 6,
      market: 'us',
      last_seen_at: '2026-03-18T09:00:00Z',
    },
  ],
  loading: false,
  stale: false,
});

vi.mock('../stores/connectionStore', () => ({
  useConnectionStore: () => connectionStore,
}));

vi.mock('../stores/newsStore', () => ({
  useNewsStore: () => newsStore,
}));

vi.mock('../stores/marketStore', () => ({
  useMarketStore: () => marketStore,
}));

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

vi.mock('../stores/topicStore', () => ({
  useTopicStore: () => topicStore,
}));

describe('DashboardView', () => {
  beforeEach(() => {
    mockPush.mockReset();
    connectionStore.state = 'live';
    connectionStore.usingMock = false;
    connectionStore.streamError = null;
  });

  it('renders terminal-style dashboard labels and live modules', () => {
    const wrapper = mount(DashboardView);
    const columnRoles = wrapper
      .findAll('[data-role^="dashboard-column-"]')
      .map((node) => node.attributes('data-role'))
      .filter((value) => value !== 'dashboard-column-scroller');

    expect(wrapper.text()).toContain('Market Control');
    expect(wrapper.text()).toContain('Control Room');
    expect(wrapper.text()).toContain('Signal Overview');
    expect(wrapper.text()).toContain('Live Movers');
    expect(wrapper.find('[data-role="dashboard-hero"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="dashboard-columns"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="dashboard-column-movers"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="dashboard-column-topics"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="dashboard-column-feed"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="dashboard-columns"]').classes()).toContain('xl:grid-cols-[1.35fr_1fr_0.72fr]');
    expect(wrapper.find('[data-role="dashboard-column-movers"]').classes()).toContain('dashboard-column--movers');
    expect(wrapper.findAll('[data-role="dashboard-column-scroller"]')).toHaveLength(3);
    expect(columnRoles).toEqual([
      'dashboard-column-feed',
      'dashboard-column-topics',
      'dashboard-column-movers',
    ]);
    expect(wrapper.text()).toContain('4 只异动');
    expect(wrapper.text()).toContain('查看全部异动');
    expect(wrapper.find('[data-role="movement-signal-board"]').exists()).toBe(true);
    expect(wrapper.findAll('[data-kind="movement-signal-row"]')).toHaveLength(2);
    expect(wrapper.findAll('[data-role="movement-preview-item"]')).toHaveLength(2);
    expect(wrapper.findAll('[data-role="dashboard-feed-item"]')).toHaveLength(1);
    expect(wrapper.find('[data-role="dashboard-status-badge"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('在线');
    expect(wrapper.text()).not.toContain('SSE 增量更新正常');
  });

  it('renders a compact debug status badge for degraded or offline states', () => {
    connectionStore.state = 'offline';
    connectionStore.streamError = 'SSE disconnected';

    const wrapper = mount(DashboardView);

    expect(wrapper.find('[data-role="dashboard-status-badge"]').text()).toContain('离线');
    expect(wrapper.find('[data-role="dashboard-status-badge"]').text()).toContain('SSE off');
    expect(wrapper.text()).not.toContain('当前处于降级或断线状态');
  });

  it('wires sentiment metrics to dedicated sentiment news routes', () => {
    const wrapper = mount(DashboardView);

    const heroLinks = wrapper.find('[data-role="hero-grid"]').findAll('a').map((node) => node.attributes('href'));

    expect(heroLinks).toContain('/news/sentiment/positive');
    expect(heroLinks).toContain('/news/sentiment/negative');
    expect(heroLinks).toContain('/watchlist');
  });

  it('renders dashboard metrics from the dashboard news slot without reload side effects', async () => {
    const wrapper = mount(DashboardView);
    await nextTick();

    expect(wrapper.text()).toContain('新闻总量');
    expect(wrapper.text()).toContain('1');
  });

  it('routes dashboard news preview rows to the news detail page on click', async () => {
    const wrapper = mount(DashboardView);

    await wrapper.get('[data-role="dashboard-feed-item"]').trigger('click');

    expect(mockPush).toHaveBeenCalledWith({ name: 'news-detail', params: { id: 1 } });
  });
});
