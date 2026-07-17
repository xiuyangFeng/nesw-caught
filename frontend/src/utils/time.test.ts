import { describe, expect, it } from 'vitest';

import {
  compareNewsTimestamps,
  getNewsDisplayTimestamp,
  getNewsTimeSourceLabel,
} from './time';

describe('time helpers', () => {
  it('falls back to fetched_at when published_at is missing', () => {
    expect(
      getNewsDisplayTimestamp({
        published_at: null,
        fetched_at: '2026-03-17T10:00:00Z',
      }),
    ).toBe('2026-03-17T10:00:00Z');
  });

  it('prefers effective_at when present', () => {
    expect(
      getNewsDisplayTimestamp({
        effective_at: '2026-03-17T11:00:00Z',
        published_at: '2026-03-17T10:00:00Z',
        fetched_at: '2026-03-17T12:00:00Z',
      }),
    ).toBe('2026-03-17T11:00:00Z');
  });

  it('labels original publish time vs fetch time', () => {
    expect(
      getNewsTimeSourceLabel({
        published_at: '2026-03-17T10:00:00Z',
        fetched_at: '2026-03-17T10:05:00Z',
      }),
    ).toBe('原文时间');
    expect(
      getNewsTimeSourceLabel({
        published_at: null,
        fetched_at: '2026-03-17T10:05:00Z',
      }),
    ).toBe('抓取时间');
  });

  it('sorts by fallback timestamp when publication time is missing', () => {
    const newerFetched = {
      published_at: null,
      fetched_at: '2026-03-17T10:05:00Z',
    };
    const olderPublished = {
      published_at: '2026-03-17T10:00:00Z',
      fetched_at: '2026-03-17T10:00:00Z',
    };

    expect(compareNewsTimestamps(olderPublished, newerFetched)).toBeGreaterThan(0);
  });
});
