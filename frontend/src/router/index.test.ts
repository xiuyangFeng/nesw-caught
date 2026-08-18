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

  it('redirects root navigation to the desk homepage', async () => {
    const { default: router } = await import('./index');

    await router.push('/');

    expect(router.currentRoute.value.path).toBe('/desk');
    expect(router.currentRoute.value.name).toBe('desk');
  });

  it('resolves the desk ops route', async () => {
    const { default: router } = await import('./index');

    await router.push('/desk/ops');

    expect(router.currentRoute.value.path).toBe('/desk/ops');
    expect(router.currentRoute.value.name).toBe('desk-ops');
  });

  it('resolves desk product pages added in later phases', async () => {
    const { default: router } = await import('./index');

    await router.push('/desk/portfolio-proposal');
    expect(router.currentRoute.value.name).toBe('desk-proposal');
    await router.push('/desk/report-card');
    expect(router.currentRoute.value.name).toBe('desk-report-card');
    await router.push('/desk/strategies');
    expect(router.currentRoute.value.name).toBe('desk-strategies');
    await router.push('/desk/backtest');
    expect(router.currentRoute.value.name).toBe('desk-backtest');
  });

  it('resolves event detail routes by event key', async () => {
    const { default: router } = await import('./index');

    await router.push('/news/events/topic-1');

    expect(router.currentRoute.value.path).toBe('/news/events/topic-1');
    expect(router.currentRoute.value.name).toBe('event-detail');
    expect(router.currentRoute.value.params).toEqual({ eventKey: 'topic-1' });
  });
});
