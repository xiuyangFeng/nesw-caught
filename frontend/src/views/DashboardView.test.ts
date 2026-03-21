import { mount } from '@vue/test-utils';
import { nextTick, reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DashboardView from './DashboardView.vue';

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
  topTopics: [],
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
}));

vi.mock('../stores/topicStore', () => ({
  useTopicStore: () => topicStore,
}));

describe('DashboardView', () => {
  beforeEach(() => {
    connectionStore.state = 'live';
    connectionStore.usingMock = false;
    connectionStore.streamError = null;
  });

  it('renders terminal-style dashboard labels and live modules', () => {
    const wrapper = mount(DashboardView);

    expect(wrapper.text()).toContain('Market Control');
    expect(wrapper.text()).toContain('Signal Overview');
    expect(wrapper.text()).toContain('Live Movers');
    expect(wrapper.find('[data-role="dashboard-hero"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="dashboard-grid"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('4 只异动');
    expect(wrapper.text()).toContain('查看全部异动');
    expect(wrapper.findAll('[data-role="movement-preview-item"]')).toHaveLength(3);
  });

  it('wires sentiment metrics to dedicated sentiment news routes', () => {
    const wrapper = mount(DashboardView);

    const links = wrapper.findAll('a').map((node) => node.attributes('href'));

    expect(links).toContain('/news/sentiment/positive');
    expect(links).toContain('/news/sentiment/negative');
  });

  it('renders dashboard metrics from the dashboard news slot without reload side effects', async () => {
    const wrapper = mount(DashboardView);
    await nextTick();

    expect(wrapper.text()).toContain('新闻总量');
    expect(wrapper.text()).toContain('1');
  });
});
