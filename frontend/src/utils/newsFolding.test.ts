import { describe, expect, it } from 'vitest';

import type { EditorialStoryEntry } from './newsEditorial';
import { partitionFoldableStream } from './newsFolding';

function makeEntries(count: number): EditorialStoryEntry[] {
  return Array.from({ length: count }, (_, index) => ({
    item: {
      id: index + 1,
      title: `t${index}`,
      source_name: 's',
      market: 'us',
      fetched_at: '2026-07-15T00:00:00Z',
    } as EditorialStoryEntry['item'],
    detail: null,
    score: count - index,
  }));
}

describe('partitionFoldableStream', () => {
  it('少于最小可见数时不折叠', () => {
    const { visible, folded } = partitionFoldableStream(makeEntries(10));
    expect(visible).toHaveLength(10);
    expect(folded).toHaveLength(0);
  });

  it('尾部低于 P70 且折叠段足够大时折叠', () => {
    const { visible, folded } = partitionFoldableStream(makeEntries(40));
    expect(visible).toHaveLength(28);
    expect(folded).toHaveLength(12);
    expect(folded[0]?.item.id).toBe(29);
  });

  it('折叠段太小(不足 3 条)时不折叠', () => {
    // 12 条:cutoff=max(10, ceil(12*0.7)=9)=10,尾部仅 2 条 < 3,不折叠
    const { visible, folded } = partitionFoldableStream(makeEntries(12));
    expect(visible).toHaveLength(12);
    expect(folded).toHaveLength(0);
  });

  it('至少保留前 10 条可见', () => {
    const { visible } = partitionFoldableStream(makeEntries(14));
    expect(visible.length).toBeGreaterThanOrEqual(10);
  });
});
