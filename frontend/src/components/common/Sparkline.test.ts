import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import Sparkline from './Sparkline.vue';

describe('Sparkline', () => {
  it('renders an svg polyline for a numeric series', () => {
    const wrapper = mount(Sparkline, {
      props: { values: [1, 3, 2, 5, 4] },
    });

    const svg = wrapper.find('[data-role="sparkline"]');
    expect(svg.exists()).toBe(true);
    expect(svg.find('polyline').exists()).toBe(true);
    expect(svg.find('polygon').exists()).toBe(true);
  });

  it('renders nothing when there are fewer than two points', () => {
    const wrapper = mount(Sparkline, {
      props: { values: [7] },
    });

    expect(wrapper.find('[data-role="sparkline"]').exists()).toBe(false);
  });

  it('handles a flat series without NaN coordinates', () => {
    const wrapper = mount(Sparkline, {
      props: { values: [2, 2, 2, 2] },
    });

    const points = wrapper.find('polyline').attributes('points') ?? '';
    expect(points).not.toContain('NaN');
    expect(points.split(' ')).toHaveLength(4);
  });

  it('maps tone to the matching css variable', () => {
    const wrapper = mount(Sparkline, {
      props: { values: [1, 2], tone: 'positive' },
    });

    expect(wrapper.find('polyline').attributes('stroke')).toBe('var(--positive)');
  });
});
