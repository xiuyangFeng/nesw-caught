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

  it('有 ai_takeaway 时显示结论行', () => {
    const entry = makeEntry();
    // takeaway 优先取 entry.detail(与 summary/topicLabel 的取值优先级一致),故 item/detail 都需带上该字段
    entry.item = { ...entry.item, ai_takeaway: '数据中心需求超预期,利好产业链' };
    entry.detail = entry.detail && { ...entry.detail, ai_takeaway: '数据中心需求超预期,利好产业链' };
    const wrapper = mount(NewsCard, { props: { entry, variant: 'stream-compact' } });
    expect(wrapper.get('[data-role="news-card-takeaway"]').text()).toContain('数据中心需求超预期');
  });

  it('无 ai_takeaway 时回退显示原文摘要且无结论行', () => {
    const wrapper = mount(NewsCard, { props: { entry: makeEntry(), variant: 'stream-compact' } });
    expect(wrapper.find('[data-role="news-card-takeaway"]').exists()).toBe(false);
    expect(wrapper.find('.summary').exists()).toBe(true);
  });

  it('read 时加淡化 class,未读时显示圆点', () => {
    const read = mount(NewsCard, { props: { entry: makeEntry(), read: true } });
    expect(read.classes()).toContain('news-card--read');
    expect(read.find('[data-role="news-card-unread"]').exists()).toBe(false);
    const unread = mount(NewsCard, { props: { entry: makeEntry() } });
    expect(unread.find('[data-role="news-card-unread"]').exists()).toBe(true);
  });

  it('selected 时加选中 class,并带 data-news-id', () => {
    const wrapper = mount(NewsCard, { props: { entry: makeEntry(), selected: true } });
    expect(wrapper.classes()).toContain('news-card--selected');
    expect(wrapper.attributes('data-news-id')).toBeDefined();
  });

  it('情绪与强度映射为色条 class', () => {
    const entry = makeEntry();
    entry.item = { ...entry.item, sentiment_label: 'negative' };
    entry.score = 1.2;
    const wrapper = mount(NewsCard, { props: { entry } });
    expect(wrapper.classes()).toContain('news-card--tone-negative');
    expect(wrapper.classes()).toContain('news-card--tier-strong');
  });
});
