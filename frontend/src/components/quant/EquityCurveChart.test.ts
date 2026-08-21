import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import EquityCurveChart from './EquityCurveChart.vue';

describe('EquityCurveChart', () => {
  it('renders an SVG polyline and area from the equity points', () => {
    const wrapper = mount(EquityCurveChart, {
      props: {
        points: [
          { date: '2026-01-05', equity: 1 },
          { date: '2026-02-05', equity: 1.05 },
          { date: '2026-03-05', equity: 0.97 },
          { date: '2026-04-05', equity: 1.08 },
        ],
      },
    });
    expect(wrapper.find('[data-role="equity-curve-line"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="equity-curve-area"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="equity-curve-final"]').text()).toContain('1.0800');
    expect(wrapper.get('[data-role="equity-curve-final"]').text()).toContain('8.00%');
  });

  it('renders nothing when there are fewer than two points', () => {
    const wrapper = mount(EquityCurveChart, {
      props: { points: [{ date: '2026-01-05', equity: 1 }] },
    });
    expect(wrapper.find('[data-role="equity-curve-chart"]').exists()).toBe(false);
  });

  it('downsamples long curves to at most 500 rendered points', () => {
    const points = Array.from({ length: 3000 }, (_, index) => ({
      date: `2026-${String(index).padStart(4, '0')}`,
      equity: 1 + index * 0.0001,
    }));
    const wrapper = mount(EquityCurveChart, { props: { points } });
    const polyline = wrapper.get('[data-role="equity-curve-line"]').attributes('points') ?? '';
    const renderedCount = polyline.split(' ').filter(Boolean).length;
    expect(renderedCount).toBeLessThanOrEqual(500);
    // 首尾保留：起止日期仍来自原始数据
    expect(wrapper.text()).toContain(points[0].date);
    expect(wrapper.text()).toContain(points[points.length - 1].date);
  });
});
