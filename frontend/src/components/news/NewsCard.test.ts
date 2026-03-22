import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { EditorialStoryEntry } from '../../utils/newsEditorial';
import NewsCard from './NewsCard.vue';

function makeEntry(): EditorialStoryEntry {
  return {
    item: {
      id: 21,
      title: 'Xinjiang power export exceeds 300 billion kilowatt-hours',
      summary: 'A short summary used to verify the homepage card stays compact and horizontal.',
      source_name: '36Kr',
      canonical_url: null,
      market: 'cn',
      sentiment_label: 'neutral',
      published_at: '2026-03-18T02:56:00Z',
      fetched_at: '2026-03-18T03:00:00Z',
    },
    detail: {
      id: 21,
      title: 'Xinjiang power export exceeds 300 billion kilowatt-hours',
      summary: 'A short summary used to verify the homepage card stays compact and horizontal.',
      source_name: '36Kr',
      canonical_url: null,
      market: 'cn',
      sentiment_label: 'neutral',
      published_at: '2026-03-18T02:56:00Z',
      fetched_at: '2026-03-18T03:00:00Z',
      sentiment_score: null,
      article: null,
      mentions: [],
      topic: {
        id: 5,
        topic_title: 'Regional infrastructure',
        importance_score: 0.66,
        last_seen_at: '2026-03-18T02:56:00Z',
      },
    },
    score: 0.66,
  };
}

describe('NewsCard', () => {
  it('renders a shared horizontal card body with copy and meta columns', () => {
    const wrapper = mount(NewsCard, {
      props: {
        entry: makeEntry(),
        variant: 'stream',
      },
    });

    expect(wrapper.find('.news-card__body').exists()).toBe(true);
    expect(wrapper.find('.news-card__meta').exists()).toBe(true);
    expect(wrapper.find('[data-role="news-card-shell"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="news-card-head"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="news-card-title"]').text()).toContain('Xinjiang power export exceeds');
  });
});
