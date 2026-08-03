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
  it('renders one stacked prompt/completion bar and label per day', () => {
    const wrapper = mount(TokenTrendChart, { props: { daily } });

    expect(wrapper.find('[data-role="chart-container"]').exists()).toBe(true);
    expect(wrapper.findAll('[data-role="token-day-bar"]')).toHaveLength(3);
    expect(wrapper.findAll('[data-role="prompt-token-segment"]')).toHaveLength(3);
    expect(wrapper.findAll('[data-role="completion-token-segment"]')).toHaveLength(3);
    expect(wrapper.text()).toContain('07-01');
    expect(wrapper.text()).toContain('07-03');
    expect(wrapper.text()).toContain('400');
  });

  it('shows token composition details for the hovered day', async () => {
    const wrapper = mount(TokenTrendChart, { props: { daily } });

    await wrapper.findAll('[data-role="token-day-bar"]')[0].trigger('mouseenter');

    expect(wrapper.text()).toContain('2026-07-01');
    expect(wrapper.text()).toContain('输入 100');
    expect(wrapper.text()).toContain('输出 200');

    await wrapper.findAll('[data-role="token-day-bar"]')[0].trigger('mouseleave');
    expect(wrapper.text()).not.toContain('输入 100');
  });

  it('renders an empty state when there is no daily data', () => {
    const wrapper = mount(TokenTrendChart, { props: { daily: [] } });

    expect(wrapper.find('[data-role="chart-container"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('暂无足够历史 Token 用量趋势数据');
  });
});
