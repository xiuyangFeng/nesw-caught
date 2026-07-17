import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getMarketSnapshots: vi.fn(),
};

vi.mock('../api/client', () => ({
  apiClient,
}));

describe('marketStore', () => {
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

  it('loads snapshots and clears loading/error on success', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useMarketStore } = await import('./marketStore');
    setActivePinia(createPinia());
    const store = useMarketStore();

    apiClient.getMarketSnapshots.mockResolvedValue({
      data: [
        {
          symbol: 'AAPL',
          is_abnormal: false,
        },
      ],
      degraded: false,
    });

    await store.loadSnapshots();

    expect(store.snapshots).toHaveLength(1);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.usingMock).toBe(false);
    expect(store.lastLoadedAt).toBeTypeOf('string');
  });

  it('sets error and resets loading to false when the request fails', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useMarketStore } = await import('./marketStore');
    setActivePinia(createPinia());
    const store = useMarketStore();

    apiClient.getMarketSnapshots.mockRejectedValue(new Error('backend offline'));

    await expect(store.loadSnapshots()).rejects.toThrow('backend offline');

    expect(store.loading).toBe(false);
    expect(store.error).toBe('backend offline');
  });
});
