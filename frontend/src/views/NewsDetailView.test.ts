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
  detailMap: { 1: detail },
  detailLoading: false,
  stale: false,
  loadDetail: vi.fn(),
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

describe('NewsDetailView', () => {
  beforeEach(() => {
    mockPush.mockReset();
    newsStore.loadDetail.mockReset();
    topicStore.loadDetail.mockReset();
  });

  it('keeps source link but hides the redundant article body section', () => {
    const wrapper = mount(NewsDetailView);

    expect(wrapper.text()).toContain('打开原文');
    expect(wrapper.text()).not.toContain('正文内容');
    expect(wrapper.text()).not.toContain('success');
  });
});
