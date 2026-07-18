import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import StockSparkline from './StockSparkline.vue';

describe('StockSparkline', () => {
  it('renders the shared SVG sparkline inside the stock sparkline shell', () => {
    const wrapper = mount(StockSparkline, {
      props: {
        prices: [100, 102, 101, 105],
      },
    });

    const shell = wrapper.get('[data-role="stock-sparkline"]');
    const svg = shell.get('[data-role="sparkline"]');
    expect(svg.element.tagName).toBe('svg');
    expect(svg.get('polyline').attributes('stroke')).toBe('var(--positive)');
  });

  it('uses the negative tone for falling prices', () => {
    const wrapper = mount(StockSparkline, {
      props: {
        prices: [105, 102, 103, 100],
      },
    });

    expect(wrapper.get('[data-role="sparkline"] polyline').attributes('stroke')).toBe('var(--negative)');
  });

  it('falls back to the accent tone for flat prices and renders nothing for insufficient data', () => {
    const flat = mount(StockSparkline, {
      props: {
        prices: [100, 100],
      },
    });
    expect(flat.get('[data-role="sparkline"] polyline').attributes('stroke')).toBe('var(--accent)');

    const empty = mount(StockSparkline, {
      props: {
        prices: [100],
      },
    });
    expect(empty.find('[data-role="sparkline"]').exists()).toBe(false);
    expect(empty.find('[data-role="stock-sparkline"]').exists()).toBe(true);
  });
});
