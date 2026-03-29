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

  it('redirects root navigation to the news discovery route', async () => {
    const { default: router } = await import('./index');

    await router.push('/');

    expect(router.currentRoute.value.path).toBe('/news');
    expect(router.currentRoute.value.name).toBe('news-feed');
  });
});
