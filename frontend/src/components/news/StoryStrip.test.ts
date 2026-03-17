import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { EditorialStoryEntry } from '../../utils/newsEditorial';
import StoryStrip from './StoryStrip.vue';

function makeEntry(): EditorialStoryEntry {
  return {
    item: {
      id: 7,
      title: 'Supporting story layout should stay compact on desktop',
      summary: 'A longer summary used to verify supporting cards render in a dedicated horizontal wrapper.',
      source_name: 'CLS Telegraph',
      canonical_url: null,
      market: 'cn',
      sentiment_label: 'neutral',
      published_at: '2026-03-18T08:00:00Z',
      fetched_at: '2026-03-18T08:05:00Z',
    },
    detail: {
      id: 7,
      title: 'Supporting story layout should stay compact on desktop',
      summary: 'A longer summary used to verify supporting cards render in a dedicated horizontal wrapper.',
      source_name: 'CLS Telegraph',
      canonical_url: null,
      market: 'cn',
      sentiment_label: 'neutral',
      published_at: '2026-03-18T08:00:00Z',
      fetched_at: '2026-03-18T08:05:00Z',
      sentiment_score: null,
      article: null,
      mentions: [],
      topic: {
        id: 3,
        topic_title: 'Oil supply chain',
        importance_score: 0.82,
        last_seen_at: '2026-03-18T08:00:00Z',
      },
    },
    score: 0.88,
  };
}

describe('StoryStrip', () => {
  it('renders supporting cards with a terminal section label and dedicated body wrapper', () => {
    const wrapper = mount(StoryStrip, {
      props: {
        title: 'Signal Queue',
        stories: [makeEntry()],
      },
    });

    expect(wrapper.find('[data-role="story-strip-label"]').text()).toBe('Signal Queue');
    expect(wrapper.find('.strip-grid').exists()).toBe(true);
    expect(wrapper.find('.news-card--supporting .news-card__supporting-body').exists()).toBe(true);
    expect(wrapper.find('.news-card--supporting .news-card__supporting-meta').exists()).toBe(true);
  });
});
