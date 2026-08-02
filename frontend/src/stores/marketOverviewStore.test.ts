import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getMarketOverview: vi.fn(),
  getMarketIndexConfig: vi.fn(),
  createMarketIndexConfig: vi.fn(),
  updateMarketIndexConfig: vi.fn(),
  deleteMarketIndexConfig: vi.fn(),
};

vi.mock('../api/client', () => ({
  apiClient,
}));

const overviewFixture = {
  generated_at: '2026-08-02T08:00:00Z',
  markets: [
    {
      market: 'us',
      display_name: '美股',
      is_open: true,
      indices: [],
      quant_sentiment: { score: 0.45, label: 'greed', inputs: null },
      boards: { status: 'ok', stale: false, source: 'preset_etf', items: [] },
      news_sentiment: { status: 'ok', score: 0.31, sample_count: 12, top_signals: [] },
    },
  ],
};

const configFixture = [
  { id: 1, symbol: '^GSPC', market: 'us', display_name: '标普500', kind: 'index', sort_order: 0, enabled: true },
];

async function createStore() {
  const { createPinia, setActivePinia } = await import('pinia');
  const { useMarketOverviewStore } = await import('./marketOverviewStore');
  setActivePinia(createPinia());
  return useMarketOverviewStore();
}

describe('marketOverviewStore', () => {
  beforeEach(() => {
    Object.values(apiClient).forEach((fn) => fn.mockReset());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads the overview and clears loading/error on success', async () => {
    const store = await createStore();
    apiClient.getMarketOverview.mockResolvedValue({ data: overviewFixture, degraded: false });

    await store.loadOverview();

    expect(store.overview).toEqual(overviewFixture);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.usingMock).toBe(false);
    expect(store.lastLoadedAt).toBeTypeOf('string');
  });

  it('captures load failures into error state without throwing (timer-safe)', async () => {
    const store = await createStore();
    apiClient.getMarketOverview.mockRejectedValue(new Error('backend offline'));

    await store.loadOverview();

    expect(store.overview).toBeNull();
    expect(store.loading).toBe(false);
    expect(store.error).toBe('backend offline');
  });

  it('marks degraded responses as mock usage', async () => {
    const store = await createStore();
    apiClient.getMarketOverview.mockResolvedValue({ data: overviewFixture, degraded: true });

    await store.loadOverview();

    expect(store.usingMock).toBe(true);
  });

  it('refreshes overview every 60s after startAutoRefresh and stops cleanly', async () => {
    vi.useFakeTimers();
    const store = await createStore();
    apiClient.getMarketOverview.mockResolvedValue({ data: overviewFixture, degraded: false });

    store.startAutoRefresh();
    expect(apiClient.getMarketOverview).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(60_000);
    expect(apiClient.getMarketOverview).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(60_000);
    expect(apiClient.getMarketOverview).toHaveBeenCalledTimes(2);

    store.stopAutoRefresh();
    await vi.advanceTimersByTimeAsync(120_000);
    expect(apiClient.getMarketOverview).toHaveBeenCalledTimes(2);
  });

  it('restarting the auto refresh does not stack timers', async () => {
    vi.useFakeTimers();
    const store = await createStore();
    apiClient.getMarketOverview.mockResolvedValue({ data: overviewFixture, degraded: false });

    store.startAutoRefresh();
    store.startAutoRefresh();

    await vi.advanceTimersByTimeAsync(60_000);
    expect(apiClient.getMarketOverview).toHaveBeenCalledTimes(1);
    store.stopAutoRefresh();
  });

  it('loads the index config list', async () => {
    const store = await createStore();
    apiClient.getMarketIndexConfig.mockResolvedValue({ data: configFixture, degraded: false });

    await store.loadIndexConfig();

    expect(store.indexConfigs).toEqual(configFixture);
    expect(store.configError).toBeNull();
  });

  it('reloads config and overview after a successful create', async () => {
    const store = await createStore();
    apiClient.createMarketIndexConfig.mockResolvedValue({ data: configFixture[0], degraded: false });
    apiClient.getMarketIndexConfig.mockResolvedValue({ data: configFixture, degraded: false });
    apiClient.getMarketOverview.mockResolvedValue({ data: overviewFixture, degraded: false });

    await store.createIndexConfig({ symbol: '^IXIC', market: 'us', display_name: '纳斯达克' });

    expect(apiClient.createMarketIndexConfig).toHaveBeenCalledWith({
      symbol: '^IXIC',
      market: 'us',
      display_name: '纳斯达克',
    });
    expect(apiClient.getMarketIndexConfig).toHaveBeenCalledTimes(1);
    expect(apiClient.getMarketOverview).toHaveBeenCalledTimes(1);
    expect(store.configSaving).toBe(false);
  });

  it('reloads config and overview after update and delete', async () => {
    const store = await createStore();
    apiClient.updateMarketIndexConfig.mockResolvedValue({ data: configFixture[0], degraded: false });
    apiClient.deleteMarketIndexConfig.mockResolvedValue({ data: undefined, degraded: false });
    apiClient.getMarketIndexConfig.mockResolvedValue({ data: configFixture, degraded: false });
    apiClient.getMarketOverview.mockResolvedValue({ data: overviewFixture, degraded: false });

    await store.updateIndexConfig(1, { enabled: false });
    await store.deleteIndexConfig(1);

    expect(apiClient.updateMarketIndexConfig).toHaveBeenCalledWith(1, { enabled: false });
    expect(apiClient.deleteMarketIndexConfig).toHaveBeenCalledWith(1);
    expect(apiClient.getMarketOverview).toHaveBeenCalledTimes(2);
  });

  it('surfaces mutation failures via configError and rethrows for the caller', async () => {
    const store = await createStore();
    apiClient.createMarketIndexConfig.mockRejectedValue(new Error('symbol conflict'));

    await expect(
      store.createIndexConfig({ symbol: '^GSPC', market: 'us', display_name: '标普500' }),
    ).rejects.toThrow('symbol conflict');

    expect(store.configError).toBe('symbol conflict');
    expect(store.configSaving).toBe(false);
    expect(apiClient.getMarketOverview).not.toHaveBeenCalled();
  });
});
