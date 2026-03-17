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
});
