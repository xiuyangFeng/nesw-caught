import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { EditorialStoryEntry } from '../../utils/newsEditorial';
import NewsCard from './NewsCard.vue';
import NewsVirtualList from './NewsVirtualList.vue';

function makeEntry(id: number): EditorialStoryEntry {
  return {
    item: {
      id,
      title: `Story ${id}`,
      summary: 'Compact stream card for virtualization regression coverage.',
      source_name: 'Reuters',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'neutral',
      published_at: '2026-03-18T08:00:00Z',
      fetched_at: '2026-03-18T08:02:00Z',
    },
    detail: null,
    score: 0.5,
  };
}

describe('NewsVirtualList', () => {
  it('renders fixed-height compact stream rows', async () => {
    const wrapper = mount(NewsVirtualList, {
      props: {
        entries: [makeEntry(1), makeEntry(2)],
      },
    });

    await Promise.resolve();

    expect(wrapper.find('.virtual-row').attributes('style')).toContain('height: 156px;');
    expect(wrapper.find('[data-role="news-card-shell"]').classes()).toContain('news-card--stream-compact');
  });

  it('forwards selectedId/readIds to NewsCard as selected/read props', async () => {
    const wrapper = mount(NewsVirtualList, {
      props: {
        entries: [makeEntry(1), makeEntry(2)],
        selectedId: 2,
        readIds: new Set([1]),
      },
    });

    await Promise.resolve();

    const cards = wrapper.findAllComponents(NewsCard);
    expect(cards[0].props('selected')).toBe(false);
    expect(cards[0].props('read')).toBe(true);
    expect(cards[1].props('selected')).toBe(true);
    expect(cards[1].props('read')).toBe(false);
  });
});
