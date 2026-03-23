import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AppShell from './AppShell.vue';

const routeState = {
  path: '/news',
};

const connectionStore = {
  state: 'live',
  lastEventAt: '2026-03-18T01:00:00Z',
  loadStreamStatus: vi.fn(async () => undefined),
  connect: vi.fn(),
  disconnect: vi.fn(),
};

const newsStore = {
  loadDashboardNews: vi.fn(async () => undefined),
  refreshDashboardNews: vi.fn(async () => false),
  upsertNews: vi.fn(),
};

const marketStore = {
  loadSnapshots: vi.fn(async () => undefined),
  upsertSnapshot: vi.fn(),
};

const topicStore = {
  loadTopics: vi.fn(async () => undefined),
  upsertTopic: vi.fn(),
};

const watchlistStore = {
  loadWatchlist: vi.fn(async () => undefined),
  marketWorkerStatus: {
    name: 'market_quote_producer',
    status: 'degraded',
    last_heartbeat_at: '2026-03-23T05:00:00Z',
    last_success_at: '2026-03-23T04:58:00Z',
    last_failure_at: '2026-03-23T04:59:00Z',
    last_error: 'provider timeout',
    cycle_count: 12,
    success_count: 11,
    failure_count: 1,
    last_quotes_count: 2,
  },
};

vi.mock('vue-router', () => ({
  RouterLink: {
    props: ['to'],
    template: '<a :href="typeof to === \'string\' ? to : to.path"><slot /></a>',
  },
  RouterView: {
    template: '<div data-role="router-view-stub">router view</div>',
  },
  useRoute: () => routeState,
}));

vi.mock('../../stores/connectionStore', () => ({
  useConnectionStore: () => connectionStore,
}));

vi.mock('../../stores/newsStore', () => ({
  useNewsStore: () => newsStore,
}));

vi.mock('../../stores/marketStore', () => ({
  useMarketStore: () => marketStore,
}));

vi.mock('../../stores/topicStore', () => ({
  useTopicStore: () => topicStore,
}));

vi.mock('../../stores/watchlistStore', () => ({
  useWatchlistStore: () => watchlistStore,
}));

describe('AppShell', () => {
  beforeEach(() => {
    routeState.path = '/news';
    connectionStore.state = 'live';
    connectionStore.lastEventAt = '2026-03-18T01:00:00Z';
    connectionStore.loadStreamStatus.mockClear();
    connectionStore.connect.mockClear();
    connectionStore.disconnect.mockClear();
    newsStore.loadDashboardNews.mockClear();
    newsStore.refreshDashboardNews.mockClear();
    newsStore.upsertNews.mockClear();
    marketStore.loadSnapshots.mockClear();
    marketStore.upsertSnapshot.mockClear();
    topicStore.loadTopics.mockClear();
    topicStore.upsertTopic.mockClear();
    watchlistStore.loadWatchlist.mockClear();
  });

  it('renders terminal shell landmarks for brand, nav, and system status', () => {
    const wrapper = mount(AppShell);

    expect(wrapper.find('[data-role="system-header"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="system-desk-chip"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="system-desk-note"]').text()).toContain('Desk / News / Topics / Movers');
    expect(wrapper.text()).not.toContain('跟踪新闻、主题热度、自选股异动与流式连接状态。');
    expect(wrapper.find('[data-role="primary-nav"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="system-status"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="shell-status-rail"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="shell-status-rail"]').text()).toContain('SSE LIVE');
    expect(wrapper.find('[data-role="shell-status-rail"]').text()).toContain('Workspace multi-market watch');
    expect(wrapper.find('[data-role="system-status"]').text()).toContain('Last event');
    expect(wrapper.find('[data-role="system-status"]').text()).toContain('market_quote_producer');
    expect(wrapper.find('[data-role="system-status"]').text()).toContain('provider timeout');
    expect(wrapper.find('[data-role="system-status"]').text()).toContain('Workspace multi-market watch');
    expect(wrapper.find('[data-role="router-view-stub"]').exists()).toBe(true);
  });

  it('uses the shared stacked layout for shell status indicator units', () => {
    const wrapper = mount(AppShell);

    expect(wrapper.find('[data-role="system-status-unit"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="market-worker-status-unit"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="system-status-unit"]').classes()).toContain('grid');
    expect(wrapper.find('[data-role="market-worker-status-unit"]').classes()).toContain('grid');
    expect(wrapper.find('[data-role="system-status-unit"]').classes()).toContain('grid-cols-1');
    expect(wrapper.find('[data-role="market-worker-status-unit"]').classes()).toContain('grid-cols-1');
    expect(wrapper.find('[data-role="market-worker-pill"]').classes()).toContain('w-full');
    expect(wrapper.find('[data-role="market-worker-shell-status"]').text()).toContain('Market worker');
    expect(wrapper.find('[data-role="market-worker-shell-status"]').text()).toContain('market_quote_producer');
  });

  it('marks the active route with a dedicated terminal signal', () => {
    routeState.path = '/news/42';

    const wrapper = mount(AppShell);

    const activeLink = wrapper.find('[data-route-active="true"]');
    expect(activeLink.exists()).toBe(true);
    expect(activeLink.text()).toContain('News Feed');
    expect(activeLink.text()).toContain('02');
    expect(activeLink.text()).toContain('MODULE');
    expect(activeLink.find('[data-role="nav-active-signal"]').exists()).toBe(true);
  });

  it('updates the shell rail signal tone when connection state is degraded', () => {
    connectionStore.state = 'degraded';

    const wrapper = mount(AppShell);

    expect(wrapper.find('[data-role="shell-status-rail"]').text()).toContain('SSE DEGRADED');
    expect(wrapper.find('[data-role="shell-status-rail-signal"]').classes()).toContain('bg-warning');
  });

  it('loads shell stores on mount and disconnects on unmount', async () => {
    const wrapper = mount(AppShell);

    expect(connectionStore.loadStreamStatus).toHaveBeenCalledTimes(1);
    expect(newsStore.loadDashboardNews).toHaveBeenCalledWith({ limit: 200 });
    expect(marketStore.loadSnapshots).toHaveBeenCalledTimes(1);
    expect(topicStore.loadTopics).toHaveBeenCalledTimes(1);
    expect(watchlistStore.loadWatchlist).toHaveBeenCalledTimes(1);

    wrapper.unmount();

    expect(connectionStore.disconnect).toHaveBeenCalledTimes(1);
  });
});
