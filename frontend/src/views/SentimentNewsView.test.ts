import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SentimentNewsView from './SentimentNewsView.vue';

const push = vi.fn();
const route = reactive({
  params: {
    sentiment: 'negative',
  },
});

const newsStore = reactive({
  sentimentItems: [
    {
      id: 7,
      title: 'Older risk story',
      summary: 'Older summary',
      source_name: 'Reuters',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'negative',
      published_at: '2026-03-18T07:00:00Z',
      fetched_at: '2026-03-18T07:05:00Z',
    },
    {
      id: 9,
      title: 'Latest risk story',
      summary: 'Latest summary',
      source_name: 'Bloomberg',
      canonical_url: null,
      market: 'hk',
      sentiment_label: 'negative',
      published_at: '2026-03-18T09:30:00Z',
      fetched_at: '2026-03-18T09:32:00Z',
    },
  ],
  detailMap: {
    7: {
      id: 7,
      title: 'Older risk story',
      summary: 'Older summary',
      source_name: 'Reuters',
      canonical_url: null,
      market: 'us',
      sentiment_label: 'negative',
      published_at: '2026-03-18T07:00:00Z',
      fetched_at: '2026-03-18T07:05:00Z',
      sentiment_score: null,
      article: null,
      mentions: [
        {
          symbol: 'TSLA',
          market: 'us',
          mention_type: 'primary',
          confidence: 0.76,
        },
      ],
      topic: null,
    },
    9: {
      id: 9,
      title: 'Latest risk story',
      summary: 'Latest summary',
      source_name: 'Bloomberg',
      canonical_url: null,
      market: 'hk',
      sentiment_label: 'negative',
      published_at: '2026-03-18T09:30:00Z',
      fetched_at: '2026-03-18T09:32:00Z',
      sentiment_score: null,
      article: null,
      mentions: [
        {
          symbol: '0700.HK',
          market: 'hk',
          mention_type: 'secondary',
          confidence: 0.88,
        },
      ],
      topic: null,
    },
  } as Record<number, any>,
  sentimentLoading: false,
  sentimentStale: false,
  usingMock: false,
  loadSentimentNews: vi.fn(async () => undefined),
  loadDetail: vi.fn(async () => undefined),
});

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({
    push,
  }),
}));

vi.mock('../stores/newsStore', () => ({
  useNewsStore: () => newsStore,
}));

describe('SentimentNewsView', () => {
  beforeEach(() => {
    push.mockReset();
    newsStore.loadSentimentNews.mockClear();
    newsStore.loadDetail.mockClear();
    route.params.sentiment = 'negative';
  });

  it('loads the requested sentiment flow, renders descending cards, and opens news detail', async () => {
    const wrapper = mount(SentimentNewsView);

    expect(newsStore.loadSentimentNews).toHaveBeenCalledWith({ sentiment_label: 'negative', limit: 300 });

    const titles = wrapper.findAll('[data-role="sentiment-news-card-title"]').map((node) => node.text());
    expect(titles).toEqual(['Latest risk story', 'Older risk story']);

    expect(wrapper.text()).toContain('Latest summary');
    expect(wrapper.text()).toContain('Bloomberg');
    expect(wrapper.text()).toContain('0700.HK');

    await wrapper.find('[data-role="sentiment-news-card"]').trigger('click');

    expect(push).toHaveBeenCalledWith({ name: 'news-detail', params: { id: 9 } });
  });
});
