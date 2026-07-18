import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getTopics: vi.fn(),
  getTopicDetail: vi.fn(),
};

vi.mock('../api/client', () => ({
  apiClient,
}));

describe('topicStore', () => {
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

  it('loads topics and clears loading/error on success', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useTopicStore } = await import('./topicStore');
    setActivePinia(createPinia());
    const store = useTopicStore();

    apiClient.getTopics.mockResolvedValue({
      data: [
        {
          id: 1,
          title: 'Topic A',
          summary: 'Summary A',
          importance_score: 0.8,
        },
      ],
      degraded: false,
    });

    await store.loadTopics();

    expect(store.topics).toHaveLength(1);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.usingMock).toBe(false);
    expect(store.lastLoadedAt).toBeTypeOf('string');
  });

  it('sets error and resets loading to false when the request fails', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useTopicStore } = await import('./topicStore');
    setActivePinia(createPinia());
    const store = useTopicStore();

    apiClient.getTopics.mockRejectedValue(new Error('backend offline'));

    await expect(store.loadTopics()).rejects.toThrow('backend offline');

    expect(store.loading).toBe(false);
    expect(store.error).toBe('backend offline');
  });
});
