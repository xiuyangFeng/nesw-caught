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
  loadNews: vi.fn(async () => undefined),
  refreshNews: vi.fn(async () => false),
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
    newsStore.loadNews.mockClear();
    newsStore.refreshNews.mockClear();
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
    expect(wrapper.find('[data-role="primary-nav"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="system-status"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="router-view-stub"]').exists()).toBe(true);
  });

  it('marks the active route with a dedicated terminal signal', () => {
    const wrapper = mount(AppShell);

    const activeLink = wrapper.find('[data-route-active="true"]');
    expect(activeLink.exists()).toBe(true);
    expect(activeLink.text()).toContain('News Feed');
    expect(activeLink.find('[data-role="nav-active-signal"]').exists()).toBe(true);
  });

  it('loads shell stores on mount and disconnects on unmount', async () => {
    const wrapper = mount(AppShell);

    expect(connectionStore.loadStreamStatus).toHaveBeenCalledTimes(1);
    expect(newsStore.loadNews).toHaveBeenCalledWith({ limit: 200 });
    expect(marketStore.loadSnapshots).toHaveBeenCalledTimes(1);
    expect(topicStore.loadTopics).toHaveBeenCalledTimes(1);
    expect(watchlistStore.loadWatchlist).toHaveBeenCalledTimes(1);

    wrapper.unmount();

    expect(connectionStore.disconnect).toHaveBeenCalledTimes(1);
  });
});
