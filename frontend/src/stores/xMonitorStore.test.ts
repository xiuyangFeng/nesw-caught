import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getXHealth: vi.fn(),
  getXAccounts: vi.fn(),
  getXPosts: vi.fn(),
  getXRadar: vi.fn(),
  refreshXPosts: vi.fn(),
  getXSearchResults: vi.fn(),
  createXAccount: vi.fn(),
  updateXAccount: vi.fn(),
  deleteXAccount: vi.fn(),
  importXAccounts: vi.fn(),
  exportXAccounts: vi.fn(),
  translateText: vi.fn(),
};

vi.mock('../api/client', () => ({
  apiClient,
}));

describe('xMonitorStore', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: vi.fn(() => null),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
      },
      configurable: true,
    });
    Object.values(apiClient).forEach((fn) => fn.mockReset());
  });

  it('tracks radar loading and stores radar payload', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useXMonitorStore } = await import('./xMonitorStore');
    setActivePinia(createPinia());
    const store = useXMonitorStore();

    apiClient.getXRadar.mockImplementation(
      () =>
        new Promise((resolve) => {
          expect(store.radarLoading).toBe(true);
          resolve({
            data: {
              priority_signals: [],
              macro_clusters: [],
              evidence_stream: [],
            },
            degraded: false,
          });
        }),
    );

    const promise = store.loadRadar();
    expect(store.radarLoading).toBe(true);
    await promise;

    expect(store.radarLoading).toBe(false);
    expect(store.radar?.priority_signals).toEqual([]);
  });

  it('reloads radar after account mutations and import', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useXMonitorStore } = await import('./xMonitorStore');
    setActivePinia(createPinia());
    const store = useXMonitorStore();

    apiClient.createXAccount.mockResolvedValue({ data: {}, degraded: false });
    apiClient.updateXAccount.mockResolvedValue({ data: {}, degraded: false });
    apiClient.deleteXAccount.mockResolvedValue({ data: undefined, degraded: false });
    apiClient.importXAccounts.mockResolvedValue({ data: { created_count: 1, updated_count: 0, skipped_count: 0 }, degraded: false });
    apiClient.getXAccounts.mockResolvedValue({ data: [], degraded: false });
    apiClient.getXPosts.mockResolvedValue({ data: [], degraded: false });
    apiClient.getXRadar.mockResolvedValue({
      data: { priority_signals: [], macro_clusters: [], evidence_stream: [] },
      degraded: false,
    });

    await store.createAccount({
      handle: 'foo',
      display_name: 'Foo',
      market_focus: 'us',
      is_active: true,
      priority: 1,
      tier: 'watch',
      notes: null,
    });
    await store.updateAccount('foo', { priority: 2 });
    await store.deleteAccount('foo');
    await store.importAccounts();

    expect(apiClient.getXRadar).toHaveBeenCalledTimes(4);
  });
});
