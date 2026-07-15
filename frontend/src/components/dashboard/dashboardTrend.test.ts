import { describe, expect, it } from 'vitest';

import { computeHourlyTrend } from './dashboardTrend';

describe('computeHourlyTrend', () => {
  it('buckets items into hourly counts, most recent hour last', () => {
    const now = Date.now();
    const items = [
      { published_at: new Date(now - 30 * 60_000).toISOString() }, // current hour bucket
      { published_at: new Date(now - 90 * 60_000).toISOString() }, // previous hour bucket
    ] as any;

    const trend = computeHourlyTrend(items, 3);

    expect(trend).toHaveLength(3);
    expect(trend[2]).toBe(1);
    expect(trend[1]).toBe(1);
    expect(trend[0]).toBe(0);
  });

  it('applies the optional predicate filter', () => {
    const now = Date.now();
    const items = [
      { published_at: new Date(now - 5 * 60_000).toISOString(), sentiment_label: 'positive' },
      { published_at: new Date(now - 5 * 60_000).toISOString(), sentiment_label: 'negative' },
    ] as any;

    const trend = computeHourlyTrend(items, 2, (item) => item.sentiment_label === 'positive');

    expect(trend[1]).toBe(1);
  });
});
