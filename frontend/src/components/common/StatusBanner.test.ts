import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import StatusBanner from './StatusBanner.vue';

describe('StatusBanner', () => {
  it('renders a terminal kicker and preserves tone semantics', () => {
    const wrapper = mount(StatusBanner, {
      props: {
        title: 'Streaming normal',
        detail: 'REST fallback remains available.',
        tone: 'success',
        kicker: 'System',
      },
    });

    expect(wrapper.attributes('data-tone')).toBe('success');
    expect(wrapper.find('[data-role="status-kicker"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="status-kicker"]').text()).toBe('System');
    expect(wrapper.find('[data-role="status-detail"]').text()).toContain('REST fallback remains available.');
  });

  it('keeps trailing actions visible next to the banner content', () => {
    const wrapper = mount(StatusBanner, {
      props: {
        title: 'Retry available',
      },
      slots: {
        default: '<button data-role="banner-action">Retry</button>',
      },
    });

    expect(wrapper.find('[data-role="banner-action"]').exists()).toBe(true);
  });
});
