import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { NewsDetail } from '../types/api';
import NewsDetailView from './NewsDetailView.vue';

const mockPush = vi.fn();

const routeState = {
  params: {
    id: '1',
  },
};

const detail: NewsDetail = {
  id: 1,
  title: '苹果首席运营官Sabih Khan现身深圳',
  summary: '今日苹果首席运营官等高管现身深圳。',
  source_name: '36Kr',
  canonical_url: 'https://example.com/full-story',
  market: 'cn',
  sentiment_label: 'neutral',
  published_at: '2026-03-17T08:01:00Z',
  fetched_at: '2026-03-17T08:05:00Z',
  sentiment_score: null,
  article: {
    content_text: '正文内容',
    extract_status: 'success',
    extract_error: null,
    extracted_at: '2026-03-17T08:03:00Z',
  },
  mentions: [],
  topic: null,
};

const newsStore = {
  detailMap: { 1: detail } as Record<number, NewsDetail>,
  detailLoading: false,
  stale: false,
  loadDetail: vi.fn(),
  loadAnalysis: vi.fn(),
};

const topicStore = {
  detailMap: {},
  loadDetail: vi.fn(),
};

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock('../stores/newsStore', () => ({
  useNewsStore: () => newsStore,
}));

vi.mock('../stores/topicStore', () => ({
  useTopicStore: () => topicStore,
}));

// NewsAiImpactCard 自行经 apiClient 取数，行为由组件单测覆盖；这里只验证接线。
vi.mock('../components/news/NewsAiImpactCard.vue', () => ({
  default: {
    props: ['newsId'],
    template: '<section data-role="news-ai-card-stub">{{ newsId }}</section>',
  },
}));

describe('NewsDetailView', () => {
  beforeEach(() => {
    mockPush.mockReset();
    newsStore.loadDetail.mockReset();
    newsStore.loadAnalysis.mockReset();
    topicStore.loadDetail.mockReset();
    newsStore.detailMap = { 1: detail };
  });

  it('keeps source link but hides the redundant article body section', () => {
    const wrapper = mount(NewsDetailView);
    const sourceAction = wrapper.get('[data-role="open-source-link"]');

    expect(wrapper.find('[data-role="news-detail-layout"]').exists()).toBe(true);
    expect(sourceAction.text()).toBe('打开原文');
    expect(sourceAction.attributes('href')).toBe('https://example.com/full-story');
    expect(sourceAction.attributes('target')).toBe('_blank');
    expect(sourceAction.attributes('rel')).toContain('noreferrer');
    expect(sourceAction.classes()).toContain('detail-primary-action');
    expect(wrapper.text()).not.toContain('正文内容');
    expect(wrapper.text()).not.toContain('success');
  });

  it('hides the source action when canonical_url is missing', () => {
    newsStore.detailMap = {
      1: {
        ...detail,
        canonical_url: null,
      },
    };

    const wrapper = mount(NewsDetailView);

    expect(wrapper.find('[data-role="open-source-link"]').exists()).toBe(false);
  });

  it('renders the AI impact card for the current news instead of the old LLM analysis card', () => {
    const wrapper = mount(NewsDetailView);

    const card = wrapper.get('[data-role="news-ai-card-stub"]');
    expect(card.text()).toBe('1');
    expect(wrapper.text()).not.toContain('LLM 标的分析');
    expect(newsStore.loadAnalysis).not.toHaveBeenCalled();
  });
});
