import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getRuntimeDiagnostic } from './runtimeDiagnostics';

describe('getRuntimeDiagnostic', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-23T08:00:00Z'));
  });

  it('prioritizes an offline SSE connection', () => {
    const diagnostic = getRuntimeDiagnostic({
      connectionState: 'offline',
      streamStatus: null,
      usingMock: false,
      marketWorkerStatus: null,
    });

    expect(diagnostic.tone).toBe('danger');
    expect(diagnostic.headline).toContain('SSE');
    expect(diagnostic.actionTarget).toBe('stream');
  });

  it('guides the user to Watchlist when the market worker is degraded', () => {
    const diagnostic = getRuntimeDiagnostic({
      connectionState: 'live',
      streamStatus: null,
      usingMock: false,
      marketWorkerStatus: {
        name: 'market_quote_producer',
        status: 'degraded',
        last_heartbeat_at: '2026-03-23T07:59:00Z',
        last_success_at: '2026-03-23T07:58:00Z',
        last_failure_at: '2026-03-23T07:59:00Z',
        last_error: 'provider timeout',
        cycle_count: 12,
        success_count: 11,
        failure_count: 1,
        last_quotes_count: 2,
      },
    });

    expect(diagnostic.tone).toBe('warning');
    expect(diagnostic.headline).toContain('market worker');
    expect(diagnostic.detail).toContain('provider timeout');
    expect(diagnostic.actionTarget).toBe('watchlist');
  });

  it('explains when the market worker has never reported runtime status', () => {
    const diagnostic = getRuntimeDiagnostic({
      connectionState: 'live',
      streamStatus: null,
      usingMock: false,
      marketWorkerStatus: null,
    });

    expect(diagnostic.tone).toBe('danger');
    expect(diagnostic.headline).toContain('未上报');
    expect(diagnostic.actionLabel).toContain('market-worker');
  });

  it('marks the worker as stale when heartbeat is too old', () => {
    const diagnostic = getRuntimeDiagnostic({
      connectionState: 'live',
      streamStatus: null,
      usingMock: false,
      marketWorkerStatus: {
        name: 'market_quote_producer',
        status: 'ok',
        last_heartbeat_at: '2026-03-23T07:40:00Z',
        last_success_at: '2026-03-23T07:40:00Z',
        last_failure_at: null,
        last_error: null,
        cycle_count: 12,
        success_count: 12,
        failure_count: 0,
        last_quotes_count: 2,
      },
    });

    expect(diagnostic.tone).toBe('warning');
    expect(diagnostic.headline).toContain('陈旧');
    expect(diagnostic.actionTarget).toBe('watchlist');
  });

  it('returns a healthy diagnostic for a fresh worker and live stream', () => {
    const diagnostic = getRuntimeDiagnostic({
      connectionState: 'live',
      streamStatus: null,
      usingMock: false,
      marketWorkerStatus: {
        name: 'market_quote_producer',
        status: 'ok',
        last_heartbeat_at: '2026-03-23T07:59:00Z',
        last_success_at: '2026-03-23T07:58:00Z',
        last_failure_at: null,
        last_error: null,
        cycle_count: 12,
        success_count: 12,
        failure_count: 0,
        last_quotes_count: 2,
      },
    });

    expect(diagnostic.tone).toBe('success');
    expect(diagnostic.actionTarget).toBe('none');
    expect(diagnostic.headline).toContain('正常');
  });
});
