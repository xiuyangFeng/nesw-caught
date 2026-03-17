import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import HeroMetrics from './HeroMetrics.vue';

describe('HeroMetrics', () => {
  it('renders terminal metric labels and tone hooks', () => {
    const wrapper = mount(HeroMetrics, {
      props: {
        metrics: [
          {
            label: 'News Count',
            value: '24',
            note: 'Current load',
            tone: 'default',
          },
        ],
      },
    });

    expect(wrapper.find('[data-role="metric-label"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="metric-value"]').text()).toBe('24');
    expect(wrapper.find('[data-role="metric-note"]').text()).toBe('Current load');
  });
});
