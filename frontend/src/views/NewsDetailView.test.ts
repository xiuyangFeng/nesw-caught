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
  analysisMap: {} as Record<number, any>,
  analysisLoadingMap: {} as Record<number, boolean>,
  analysisErrorMap: {} as Record<number, string | null>,
  detailLoading: false,
  stale: false,
  loadDetail: vi.fn(),
  loadAnalysis: vi.fn(),
  analyzeNews: vi.fn(),
};

const topicStore = {
  detailMap: {},
  loadDetail: vi.fn(),
};

const llmStore = {
  config: null as any,
  loadConfig: vi.fn(),
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

vi.mock('../stores/llmStore', () => ({
  useLlmStore: () => llmStore,
}));

describe('NewsDetailView', () => {
  beforeEach(() => {
    mockPush.mockReset();
    newsStore.loadDetail.mockReset();
    newsStore.loadAnalysis.mockReset();
    newsStore.analyzeNews.mockReset();
    topicStore.loadDetail.mockReset();
    llmStore.loadConfig.mockReset();
    newsStore.analysisMap = {};
    newsStore.analysisLoadingMap = {};
    newsStore.analysisErrorMap = {};
    llmStore.config = null;
  });

  it('keeps source link but hides the redundant article body section', () => {
    const wrapper = mount(NewsDetailView);

    expect(wrapper.text()).toContain('打开原文');
    expect(wrapper.text()).not.toContain('正文内容');
    expect(wrapper.text()).not.toContain('success');
  });

  it('shows an explicit empty state when llm is not configured', () => {
    llmStore.config = {
      configured: false,
      provider_name: null,
      display_name: null,
      model_name: null,
      base_url: null,
      api_key_set: false,
      updated_at: null,
    };

    const wrapper = mount(NewsDetailView);

    expect(wrapper.text()).toContain('尚未配置 LLM');
  });

  it('renders the top pick and recommendation reason when analysis exists', () => {
    llmStore.config = {
      configured: true,
      provider_name: 'openai_compatible',
      display_name: 'OpenAI Compatible',
      model_name: 'deepseek-chat',
      base_url: 'https://example-llm.test/v1',
      api_key_set: true,
      updated_at: '2026-03-17T09:00:00Z',
    };
    newsStore.analysisMap = {
      1: {
        news_id: 1,
        provider_name: 'openai_compatible',
        model_name: 'deepseek-chat',
        analysis_status: 'success',
        top_pick: {
          symbol: 'AAPL',
          market: 'us',
          company_name: 'Apple',
          confidence: 0.81,
          reason: '供应链波动最直接映射到 Apple 的短期预期修正。',
        },
        candidates: [
          {
            symbol: 'AAPL',
            market: 'us',
            company_name: 'Apple',
            confidence: 0.81,
            reason: '供应链波动最直接映射到 Apple 的短期预期修正。',
          },
        ],
        summary: '供应链波动首先传导到 Apple。',
        risk_notes: '单一来源新闻仍需二次验证。',
        sentiment: 'negative',
        context_limitations: null,
        analyzed_at: '2026-03-17T09:10:00Z',
        analysis_error: null,
      },
    };

    const wrapper = mount(NewsDetailView);

    expect(wrapper.text()).toContain('AAPL');
    expect(wrapper.text()).toContain('供应链波动最直接映射到 Apple 的短期预期修正。');
  });
});
