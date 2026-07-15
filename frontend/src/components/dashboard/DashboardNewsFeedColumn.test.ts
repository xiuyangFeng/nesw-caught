import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import DashboardNewsFeedColumn from './DashboardNewsFeedColumn.vue';

const routerLinkStub = {
  props: ['to'],
  template: '<a :href="typeof to === \'string\' ? to : to?.path"><slot /></a>',
};

function buildItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    title: 'AI infrastructure names lead the session',
    summary: 'Lead item summary',
    source_name: 'Bloomberg',
    canonical_url: null,
    market: 'us',
    sentiment_label: 'positive',
    published_at: '2026-03-18T08:00:00Z',
    fetched_at: '2026-03-18T08:03:00Z',
    ...overrides,
  };
}

describe('DashboardNewsFeedColumn', () => {
  it('renders feed items and emits selectNews on click', async () => {
    const wrapper = mount(DashboardNewsFeedColumn, {
      props: {
        items: [buildItem()] as any,
        loading: false,
      },
      global: { stubs: { RouterLink: routerLinkStub } },
    });

    const feedItem = wrapper.find('[data-role="dashboard-feed-item"]');
    expect(feedItem.exists()).toBe(true);
    expect(wrapper.text()).toContain('AI infrastructure names lead the session');

    await feedItem.trigger('click');
    expect(wrapper.emitted('selectNews')?.[0]).toEqual([1]);
  });

  it('caps the visible list at 8 items while keeping the empty check on the full list', () => {
    const items = Array.from({ length: 10 }, (_, index) => buildItem({ id: index + 1 }));
    const wrapper = mount(DashboardNewsFeedColumn, {
      props: { items: items as any, loading: false },
      global: { stubs: { RouterLink: routerLinkStub } },
    });

    expect(wrapper.findAll('[data-role="dashboard-feed-item"]')).toHaveLength(8);
  });

  it('marks high editorial_score items as breaking with a pulsing indicator', () => {
    const wrapper = mount(DashboardNewsFeedColumn, {
      props: {
        items: [buildItem({ id: 2, editorial_score: 9.0 })] as any,
        loading: false,
      },
      global: { stubs: { RouterLink: routerLinkStub } },
    });

    const feedItem = wrapper.find('[data-role="dashboard-feed-item"]');
    expect(feedItem.classes()).toContain('dashboard-feed-item--breaking');
    expect(feedItem.find('.animate-pulse').exists()).toBe(true);
  });
});
