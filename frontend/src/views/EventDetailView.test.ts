import { flushPromises, mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { HttpError } from '../api/http';
import EventDetailView from './EventDetailView.vue';

const mockPush = vi.fn();
const { getNewsEventDetail } = vi.hoisted(() => ({
  getNewsEventDetail: vi.fn(),
}));
const routeState = reactive({
  params: {
    eventKey: 'topic-1',
  },
});

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock('../api/client', () => ({
  apiClient: {
    getNewsEventDetail,
  },
}));

describe('EventDetailView', () => {
  beforeEach(() => {
    mockPush.mockReset();
    routeState.params.eventKey = 'topic-1';
    getNewsEventDetail.mockReset();
    getNewsEventDetail.mockResolvedValue({
      degraded: false,
      data: {
        event_key: 'topic-1',
        event_title: 'AI Chip Launch',
        event_summary: 'NVIDIA 新一轮 AI 芯片发布带动供应链关注度上升。',
        event_type: 'product',
        market: 'us',
        sentiment_label: 'positive',
        importance_score: 0.93,
        last_seen_at: '2026-03-18T08:12:00Z',
        primary_symbol: 'NVDA',
        related_symbols: ['NVDA', 'SMCI'],
        source_count: 3,
        news_count: 3,
        news_items: [
          {
            id: 1,
            title: 'Late fetched source',
            summary: 'Fallback to fetched_at.',
            source_name: 'Reuters',
            canonical_url: 'https://example.com/reuters',
            market: 'us',
            sentiment_label: 'neutral',
            published_at: null,
            fetched_at: '2026-03-18T08:03:00Z',
          },
          {
            id: 2,
            title: 'Published later',
            summary: 'Should sort first.',
            source_name: 'Bloomberg',
            canonical_url: null,
            market: 'us',
            sentiment_label: 'positive',
            published_at: '2026-03-18T08:10:00Z',
            fetched_at: '2026-03-18T08:11:00Z',
          },
          {
            id: 3,
            title: 'No timestamp',
            summary: null,
            source_name: 'CLS',
            canonical_url: null,
            market: 'us',
            sentiment_label: 'neutral',
            published_at: null,
            fetched_at: null,
          },
        ],
      },
    });
  });

  it('renders a compact event header and timeline metadata using backend order', async () => {
    const wrapper = mount(EventDetailView);
    await flushPromises();

    expect(getNewsEventDetail).toHaveBeenCalledWith('topic-1');
    expect(wrapper.text()).toContain('AI Chip Launch');
    expect(wrapper.text()).toContain('NVIDIA 新一轮 AI 芯片发布带动供应链关注度上升。');
    expect(wrapper.text()).toContain('PRODUCT');
    expect(wrapper.text()).toContain('偏利好');
    expect(wrapper.text()).toContain('US');
    expect(wrapper.text()).toContain('NVDA');
    expect(wrapper.text()).toContain('SMCI');
    expect(wrapper.text()).toContain('Sources 3');
    expect(wrapper.text()).toContain('News 3');
    expect(wrapper.text()).toContain('03/18 04:12 ET');
    expect(wrapper.findAll('[data-role="event-stage-label"]').map((node) => node.text())).toEqual(['首发', '跟进', '更新']);
    expect(wrapper.findAll('[data-role="event-source-name"]').map((node) => node.text())).toEqual(['Reuters', 'Bloomberg', 'CLS']);
    expect(wrapper.findAll('[data-role="event-sentiment-pill"]').map((node) => node.text())).toEqual(['中性', '偏利好', '中性']);

    const timelineTitles = wrapper.findAll('[data-role="event-timeline-title"]').map((node) => node.text());
    expect(timelineTitles).toEqual(['Late fetched source', 'Published later', 'No timestamp']);
    expect(wrapper.text()).toContain('摘要待补充');
  });

  it('routes timeline items to the news detail page and keeps source links optional', async () => {
    const wrapper = mount(EventDetailView);
    await flushPromises();

    expect(wrapper.findAll('[data-role="event-open-source-link"]')).toHaveLength(1);
    expect(wrapper.get('[data-role="event-open-source-link"]').attributes('href')).toBe('https://example.com/reuters');

    const detailButtons = wrapper.findAll('[data-role="event-open-news-detail"]');
    expect(detailButtons).toHaveLength(3);

    await detailButtons[1].trigger('click');

    expect(mockPush).toHaveBeenCalledWith({ name: 'news-detail', params: { id: 2 } });
  });

  it('shows a not-found state when the backend returns 404', async () => {
    getNewsEventDetail.mockRejectedValue(new HttpError('event not found', 404));

    const wrapper = mount(EventDetailView);
    await flushPromises();

    expect(wrapper.text()).toContain('事件已不存在，或已发生聚合变化');
  });

  it('shows a generic error state for non-404 failures', async () => {
    getNewsEventDetail.mockRejectedValue(new Error('backend offline'));

    const wrapper = mount(EventDetailView);
    await flushPromises();

    expect(wrapper.text()).toContain('加载事件详情失败');
  });

  it('renders a return action back to latest events', async () => {
    const wrapper = mount(EventDetailView);
    await flushPromises();

    await wrapper.get('[data-role="event-detail-back"]').trigger('click');

    expect(mockPush).toHaveBeenCalledWith({ name: 'news-feed' });
  });
});
