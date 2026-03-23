import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/sse', () => ({
  createStreamConnection: vi.fn(() => ({
    close: vi.fn(),
  })),
}));

describe('connectionStore', () => {
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
  });

  it('applies runtime stream status and derives the initial connection state', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useConnectionStore } = await import('./connectionStore');
    setActivePinia(createPinia());
    const store = useConnectionStore();

    store.applyStreamStatus(
      {
        mode: 'sse',
        status: 'ok',
        backend: 'hybrid',
        redis_enabled: true,
        last_published_at: null,
        last_event_name: 'news.created',
        last_error: null,
        market_worker: null,
      },
      true,
    );

    expect(store.streamStatus?.backend).toBe('hybrid');
    expect(store.usingMock).toBe(true);
    expect(store.state).toBe('degraded');
  });
});
