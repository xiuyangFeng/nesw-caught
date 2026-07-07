import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import TokenTrendChart from './TokenTrendChart.vue';
import type { TokenDailyStats } from './types';

const daily: TokenDailyStats[] = [
  { date: '2026-07-01', prompt_tokens: 100, completion_tokens: 200, total_tokens: 300 },
  { date: '2026-07-02', prompt_tokens: 150, completion_tokens: 250, total_tokens: 400 },
  { date: '2026-07-03', prompt_tokens: 50, completion_tokens: 100, total_tokens: 150 },
];

describe('TokenTrendChart', () => {
  it('renders the svg trend line with one dot and label per day', () => {
    const wrapper = mount(TokenTrendChart, { props: { daily } });

    expect(wrapper.find('[data-role="chart-container"]').exists()).toBe(true);
    expect(wrapper.findAll('circle')).toHaveLength(3);
    // X 轴标签展示 MM-DD
    expect(wrapper.text()).toContain('07-01');
    expect(wrapper.text()).toContain('07-03');
    // Y 轴最大值
    expect(wrapper.text()).toContain('400');

    const linePath = wrapper.findAll('path').find((p) => p.attributes('stroke') === '#22d3ee');
    expect(linePath).toBeTruthy();
    expect(linePath!.attributes('d')).toMatch(/^M /);
  });

  it('shows a tooltip for the hovered point on mousemove', async () => {
    const wrapper = mount(TokenTrendChart, { props: { daily } });

    const svg = wrapper.find('svg');
    (svg.element as unknown as HTMLElement).getBoundingClientRect = () =>
      ({ left: 0, width: 500, top: 0, height: 140 }) as DOMRect;
    await svg.trigger('mousemove', { clientX: 0 });

    expect(wrapper.text()).toContain('2026-07-01');
    expect(wrapper.text()).toContain('Total:');

    await svg.trigger('mouseleave');
    expect(wrapper.text()).not.toContain('Total:');
  });

  it('renders an empty state when there is no daily data', () => {
    const wrapper = mount(TokenTrendChart, { props: { daily: [] } });

    expect(wrapper.find('[data-role="chart-container"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('暂无足够历史 Token 用量趋势数据');
  });
});
