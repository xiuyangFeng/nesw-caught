import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getStreamStatus: vi.fn(),
};

vi.mock('../api/client', () => ({
  apiClient,
}));

describe('runtimeStatusStore', () => {
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
    apiClient.getStreamStatus.mockReset();
  });

  it('loads stream status and exposes market worker status', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useRuntimeStatusStore } = await import('./runtimeStatusStore');
    setActivePinia(createPinia());
    const store = useRuntimeStatusStore();

    apiClient.getStreamStatus.mockResolvedValue({
      data: {
        mode: 'sse',
        status: 'ok',
        backend: 'hybrid',
        redis_enabled: true,
        last_published_at: null,
        last_event_name: null,
        last_error: null,
        market_worker: {
          name: 'market_quote_producer',
          status: 'ok',
          last_heartbeat_at: '2026-03-23T05:00:00Z',
          last_success_at: '2026-03-23T04:58:00Z',
          last_failure_at: null,
          last_error: null,
          cycle_count: 12,
          success_count: 12,
          failure_count: 0,
          last_quotes_count: 2,
        },
      },
      degraded: false,
    });

    await store.loadRuntimeStatus();

    expect(apiClient.getStreamStatus).toHaveBeenCalledTimes(1);
    expect(store.streamStatus?.backend).toBe('hybrid');
    expect(store.marketWorkerStatus?.status).toBe('ok');
    expect(store.usingMock).toBe(false);
    expect(store.lastLoadedAt).toBeTypeOf('string');
    expect(store.error).toBeNull();
  });

  it('skips a second runtime refresh while the snapshot is still fresh', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useRuntimeStatusStore } = await import('./runtimeStatusStore');
    setActivePinia(createPinia());
    const store = useRuntimeStatusStore();

    apiClient.getStreamStatus.mockResolvedValue({
      data: {
        mode: 'sse',
        status: 'ok',
        backend: 'hybrid',
        redis_enabled: true,
        last_published_at: null,
        last_event_name: null,
        last_error: null,
        market_worker: null,
      },
      degraded: false,
    });

    await store.loadRuntimeStatusIfStale();
    await store.loadRuntimeStatusIfStale();

    expect(apiClient.getStreamStatus).toHaveBeenCalledTimes(1);
  });

  it('refreshes runtime status again after the freshness window expires', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useRuntimeStatusStore } = await import('./runtimeStatusStore');
    setActivePinia(createPinia());
    const store = useRuntimeStatusStore();

    apiClient.getStreamStatus.mockResolvedValue({
      data: {
        mode: 'sse',
        status: 'ok',
        backend: 'hybrid',
        redis_enabled: true,
        last_published_at: null,
        last_event_name: null,
        last_error: null,
        market_worker: null,
      },
      degraded: false,
    });

    await store.loadRuntimeStatus();
    store.lastLoadedAt = new Date(Date.now() - 16_000).toISOString();
    await store.loadRuntimeStatusIfStale();

    expect(apiClient.getStreamStatus).toHaveBeenCalledTimes(2);
  });
});
