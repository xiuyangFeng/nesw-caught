import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('router', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('localStorage', {
      getItem: () => null,
      setItem: () => undefined,
      removeItem: () => undefined,
    });
  });

  beforeEach(async () => {
    const { default: router } = await import('./index');
    await router.push('/dashboard');
    await router.isReady();
  });

  it('redirects root navigation to the dashboard', async () => {
    const { default: router } = await import('./index');

    await router.push('/news');
    await router.push('/');

    expect(router.currentRoute.value.path).toBe('/dashboard');
    expect(router.currentRoute.value.name).toBe('dashboard');
  });

  it('sends bookmarks of removed pages back to the dashboard', async () => {
    const { default: router } = await import('./index');

    for (const removed of ['/desk', '/desk/stocks/600519.SH', '/chat', '/x-monitor', '/analytics/backtest', '/eval/sentiment']) {
      await router.push('/news');
      await router.push(removed);
      expect(router.currentRoute.value.path).toBe('/dashboard');
    }
  });

  it('resolves event detail routes by event key', async () => {
    const { default: router } = await import('./index');

    await router.push('/news/events/topic-1');

    expect(router.currentRoute.value.path).toBe('/news/events/topic-1');
    expect(router.currentRoute.value.name).toBe('event-detail');
    expect(router.currentRoute.value.params).toEqual({ eventKey: 'topic-1' });
  });
});
