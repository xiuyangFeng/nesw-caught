import { describe, expect, it } from 'vitest';

import type { NewsDetail, NewsItem } from '../types/api';
import { groupEditorialStories, rankEditorialStories } from './newsEditorial';

function makeItem(overrides: Partial<NewsItem> & Pick<NewsItem, 'id' | 'title' | 'published_at'>): NewsItem {
  return {
    id: overrides.id,
    title: overrides.title,
    summary: overrides.summary ?? null,
    source_name: overrides.source_name ?? 'Test Source',
    canonical_url: overrides.canonical_url ?? null,
    market: overrides.market ?? 'hk',
    sentiment_label: overrides.sentiment_label ?? 'neutral',
    published_at: overrides.published_at,
    fetched_at: overrides.fetched_at ?? overrides.published_at,
  };
}

function makeDetail(item: NewsItem, overrides: Partial<NewsDetail> = {}): NewsDetail {
  return {
    ...item,
    sentiment_score: overrides.sentiment_score ?? null,
    article: overrides.article ?? null,
    mentions: overrides.mentions ?? [],
    topic: overrides.topic ?? null,
  };
}

describe('rankEditorialStories', () => {
  it('prefers higher importance over merely newer low-context news', () => {
    const lowImportanceNewer = makeItem({
      id: 1,
      title: 'Low importance flash',
      summary: null,
      published_at: '2026-03-16T12:00:00Z',
    });
    const highImportanceOlder = makeItem({
      id: 2,
      title: 'High importance feature',
      summary: 'Full context summary',
      published_at: '2026-03-16T10:00:00Z',
    });

    const ranked = rankEditorialStories(
      [lowImportanceNewer, highImportanceOlder],
      {
        1: null,
        2: makeDetail(highImportanceOlder, {
          topic: {
            id: 9,
            topic_title: 'Important topic',
            importance_score: 0.92,
            last_seen_at: '2026-03-16T10:30:00Z',
          },
          mentions: [{ symbol: '0700.HK', market: 'hk', mention_type: 'primary', confidence: 0.91 }],
        }),
      },
    );

    expect(ranked[0].item.id).toBe(2);
  });

  it('uses recency to break ties between otherwise similar stories', () => {
    const older = makeItem({
      id: 3,
      title: 'Comparable older story',
      summary: 'Summary',
      published_at: '2026-03-16T08:00:00Z',
    });
    const newer = makeItem({
      id: 4,
      title: 'Comparable newer story',
      summary: 'Summary',
      published_at: '2026-03-16T11:30:00Z',
    });

    const ranked = rankEditorialStories([older, newer], { 3: null, 4: null });

    expect(ranked[0].item.id).toBe(4);
  });

  it('keeps missing-detail stories in a stable lower-confidence fallback tier', () => {
    const withDetail = makeItem({
      id: 5,
      title: 'Context-rich story',
      summary: 'Summary',
      published_at: '2026-03-16T09:00:00Z',
    });
    const noDetail = makeItem({
      id: 6,
      title: 'No detail story',
      summary: null,
      published_at: '2026-03-16T09:05:00Z',
    });

    const ranked = rankEditorialStories(
      [noDetail, withDetail],
      {
        5: makeDetail(withDetail, {
          topic: {
            id: 10,
            topic_title: 'Context topic',
            importance_score: 0.61,
            last_seen_at: '2026-03-16T09:00:00Z',
          },
        }),
        6: null,
      },
    );

    expect(ranked[0].item.id).toBe(5);
    expect(ranked[1].detail).toBeNull();
  });
});

describe('groupEditorialStories', () => {
  it('returns a lead story, bounded supporting set, and remaining stream', () => {
    const items = [
      makeItem({ id: 11, title: 'Lead', summary: 'Lead summary', published_at: '2026-03-16T10:00:00Z' }),
      makeItem({ id: 12, title: 'Support 1', summary: 'Summary', published_at: '2026-03-16T09:50:00Z' }),
      makeItem({ id: 13, title: 'Support 2', summary: 'Summary', published_at: '2026-03-16T09:40:00Z' }),
      makeItem({ id: 14, title: 'Support 3', summary: 'Summary', published_at: '2026-03-16T09:30:00Z' }),
      makeItem({ id: 15, title: 'Stream 1', summary: 'Summary', published_at: '2026-03-16T09:20:00Z' }),
      makeItem({ id: 16, title: 'Stream 2', summary: 'Summary', published_at: '2026-03-16T09:10:00Z' }),
    ];

    const grouped = groupEditorialStories(items, {}, { supportingCount: 3 });

    expect(grouped.lead?.item.id).toBe(11);
    expect(grouped.supporting).toHaveLength(3);
    expect(grouped.stream.map((entry) => entry.item.id)).toEqual([15, 16]);
  });
});
