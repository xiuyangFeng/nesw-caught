import { mount, flushPromises } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WatchlistView from './WatchlistView.vue';

const push = vi.fn();

const watchlistStore = reactive({
  candidates: [
    { symbol: '0700.HK', market: 'hk', display_name: 'Tencent', aliases: ['腾讯', '腾讯控股'] },
    { symbol: 'TME', market: 'us', display_name: 'Tencent Music', aliases: ['腾讯音乐'] },
    { symbol: 'AAPL', market: 'us', display_name: 'Apple', aliases: ['苹果'] },
  ],
  items: [
    { id: 1, symbol: '0700.HK', market: 'hk', display_name: 'Tencent', is_active: true, alert_threshold: 3, alert_mode: 'fixed' },
  ],
  quotes: [],
  relatedNews: {},
  selectedSymbol: '0700.HK',
  stale: false,
  loading: false,
  relatedLoading: false,
  detailLoading: false,
  createLoading: false,
  createError: null,
  candidateError: null,
  deleteLoadingSymbol: null,
  deleteError: null,
  loadCandidates: vi.fn(async () => undefined),
  loadWatchlist: vi.fn(async () => undefined),
  loadRelatedNews: vi.fn(async () => undefined),
  createWatchlist: vi.fn(async () => undefined),
  deleteWatchlist: vi.fn(async () => undefined),
});

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push,
  }),
}));

vi.mock('../stores/watchlistStore', () => ({
  useWatchlistStore: () => watchlistStore,
}));

describe('WatchlistView', () => {
  beforeEach(() => {
    push.mockReset();
    watchlistStore.loadCandidates.mockClear();
    watchlistStore.loadWatchlist.mockClear();
    watchlistStore.loadRelatedNews.mockClear();
    watchlistStore.createWatchlist.mockClear();
    watchlistStore.deleteWatchlist.mockClear();
  });

  it('renders the merged search-add toolbar and shows candidate results', async () => {
    const wrapper = mount(WatchlistView);
    await flushPromises();

    expect(watchlistStore.loadCandidates).toHaveBeenCalled();
    const searchInput = wrapper.get('input[placeholder="输入股票代码、中文名或英文名"]');
    await searchInput.setValue('腾');

    expect(wrapper.text()).toContain('Tencent');
    expect(wrapper.text()).toContain('Tencent Music');
    expect(wrapper.text()).toContain('已添加');
  });
});
