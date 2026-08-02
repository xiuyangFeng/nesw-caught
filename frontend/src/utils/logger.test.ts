import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The module keeps its queue/timer/rate-limit state at module scope, so each
// test re-imports it fresh (vi.resetModules) to avoid bleed-over between
// cases — the same approach api/client.test.ts uses for env stubbing.
async function loadLogger() {
  vi.resetModules();
  return import('./logger');
}

describe('logger leveled console output', () => {
  beforeEach(() => {
    // A couple of these tests exercise error() in prod, which schedules a
    // real flush timer. Fake timers keep that from lingering as a live
    // setTimeout past the end of the test.
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('logs every level to console in dev', async () => {
    vi.stubEnv('DEV', true);
    const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { logger } = await loadLogger();
    logger.debug('debug msg');
    logger.info('info msg');
    logger.warn('warn msg');
    logger.error('error msg');

    expect(debugSpy).toHaveBeenCalledWith('debug msg');
    expect(infoSpy).toHaveBeenCalledWith('info msg');
    expect(warnSpy).toHaveBeenCalledWith('warn msg');
    expect(errorSpy).toHaveBeenCalledWith('error msg');
  });

  it('only logs warn/error to console in prod (debug/info are silent)', async () => {
    vi.stubEnv('DEV', false);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }));
    const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { logger } = await loadLogger();
    logger.debug('debug msg');
    logger.info('info msg');
    logger.warn('warn msg');
    logger.error('error msg');

    expect(debugSpy).not.toHaveBeenCalled();
    expect(infoSpy).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledWith('warn msg');
    expect(errorSpy).toHaveBeenCalledWith('error msg');

    // Drain the report queue this test's error() call scheduled. The module
    // keeps a lingering `pagehide` listener on the shared jsdom `window` for
    // the lifetime of the test file (nothing ever calls removeEventListener),
    // so an empty queue here is what keeps a later pagehide test from also
    // observing this instance's stale entry.
    await vi.advanceTimersByTimeAsync(5_000);
  });

  it('extracts message/stack from an Error passed to error()', async () => {
    vi.stubEnv('DEV', true);
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { logger } = await loadLogger();

    const err = new Error('boom');
    logger.error('context message', err);

    expect(errorSpy).toHaveBeenCalledWith('context message', err);
  });
});

describe('logger error reporting: batching and rate limit', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('does not report at all in dev, even after the flush interval elapses', async () => {
    vi.stubEnv('DEV', true);
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(console, 'error').mockImplementation(() => {});

    const { logger } = await loadLogger();
    logger.error('should stay local', new Error('boom'));
    await vi.advanceTimersByTimeAsync(10_000);

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('flushes automatically ~5s after the first queued entry', async () => {
    vi.stubEnv('DEV', false);
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ accepted: 1, dropped: 0 }) });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(console, 'error').mockImplementation(() => {});

    const { logger } = await loadLogger();
    logger.error('delayed report');

    expect(fetchMock).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(5_000);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/logs/frontend');
    const body = JSON.parse(init.body as string);
    expect(body.entries).toHaveLength(1);
    expect(body.entries[0]).toMatchObject({ level: 'error', message: 'delayed report' });
  });

  it('flushes immediately once 10 entries accumulate, without waiting for the timer', async () => {
    vi.stubEnv('DEV', false);
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ accepted: 10, dropped: 0 }) });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(console, 'error').mockImplementation(() => {});

    const { logger } = await loadLogger();
    for (let i = 0; i < 10; i += 1) {
      logger.error(`err ${i}`);
    }
    await vi.advanceTimersByTimeAsync(0);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.entries).toHaveLength(10);
  });

  it('rate-limits to 30 queued entries per minute and silently drops the rest', async () => {
    vi.stubEnv('DEV', false);
    const sentBatchSizes: number[] = [];
    const fetchMock = vi.fn().mockImplementation(async (_url: string, init: RequestInit) => {
      const body = JSON.parse(init.body as string);
      sentBatchSizes.push(body.entries.length);
      return { ok: true, json: async () => ({ accepted: body.entries.length, dropped: 0 }) };
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(console, 'error').mockImplementation(() => {});

    const { logger } = await loadLogger();
    for (let i = 0; i < 45; i += 1) {
      logger.error(`err ${i}`);
    }
    await vi.advanceTimersByTimeAsync(5_000);

    const totalSent = sentBatchSizes.reduce((sum, n) => sum + n, 0);
    expect(totalSent).toBeLessThanOrEqual(30);
  });
});

describe('logger error reporting: failure is silent', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('does not throw and does not recursively log when the network request rejects', async () => {
    vi.stubEnv('DEV', false);
    const fetchMock = vi.fn().mockRejectedValue(new Error('network down'));
    vi.stubGlobal('fetch', fetchMock);
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { logger } = await loadLogger();
    expect(() => logger.error('will fail to report')).not.toThrow();

    await vi.advanceTimersByTimeAsync(5_000);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    // Only the original call logged to console — no secondary "logger itself
    // failed" message was ever emitted (that would recurse).
    expect(errorSpy).toHaveBeenCalledTimes(1);
    expect(errorSpy).toHaveBeenCalledWith('will fail to report');
  });

  it('does not throw when the backend responds with a non-2xx status', async () => {
    vi.stubEnv('DEV', false);
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(console, 'error').mockImplementation(() => {});

    const { logger } = await loadLogger();
    expect(() => logger.error('server rejected')).not.toThrow();

    await vi.advanceTimersByTimeAsync(5_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('flushes the remaining queue with authenticated keepalive fetch on pagehide', async () => {
    vi.stubEnv('DEV', false);
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(console, 'error').mockImplementation(() => {});

    const { logger } = await loadLogger();
    logger.error('about to unload');

    window.dispatchEvent(new Event('pagehide'));
    await vi.advanceTimersByTimeAsync(0);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/logs/frontend');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: 'POST',
      keepalive: true,
    });
    expect(fetchMock.mock.calls[0][1].headers).toMatchObject({
      'Content-Type': 'application/json',
    });
  });
});
