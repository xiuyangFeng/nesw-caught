import { describe, expect, it } from 'vitest';

import { compareNewsTimestamps, getNewsDisplayTimestamp } from './time';

describe('time helpers', () => {
  it('falls back to fetched_at when published_at is missing', () => {
    expect(
      getNewsDisplayTimestamp({
        published_at: null,
        fetched_at: '2026-03-17T10:00:00Z',
      }),
    ).toBe('2026-03-17T10:00:00Z');
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
