import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import SectionCard from './SectionCard.vue';

describe('SectionCard', () => {
  it('renders an optional terminal eyebrow above the title', () => {
    const wrapper = mount(SectionCard, {
      props: {
        title: 'Signal Queue',
        subtitle: 'Latest market-moving stories',
        eyebrow: 'News Feed',
      },
      slots: {
        default: '<div>content</div>',
      },
    });

    expect(wrapper.find('[data-role="section-eyebrow"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="section-eyebrow"]').text()).toBe('News Feed');
  });

  it('keeps the actions slot and compact marker available for dense layouts', () => {
    const wrapper = mount(SectionCard, {
      props: {
        title: 'Watchlist',
        compact: true,
      },
      slots: {
        actions: '<button data-role="actions-slot">Refresh</button>',
        default: '<div>content</div>',
      },
    });

    expect(wrapper.attributes('data-compact')).toBe('true');
    expect(wrapper.find('[data-role="actions-slot"]').exists()).toBe(true);
  });
});
