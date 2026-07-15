import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { BacktestSummary } from '../types/api';
import SignalBacktestView from './SignalBacktestView.vue';

const { getBacktestSummary } = vi.hoisted(() => ({
  getBacktestSummary: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: {
    getBacktestSummary,
  },
}));

const summary: BacktestSummary = {
  evaluable_count: 80,
  evaluable_rate: 0.8,
  generated_at: '2026-07-14T00:00:00Z',
  horizon: '1d',
  importance_buckets: [
    { avg_forward_return: 0.021, bucket: 'high', sample_count: 30 },
    { avg_forward_return: -0.008, bucket: 'low', sample_count: 20 },
  ],
  market: null,
  negative: { avg_forward_return: -0.015, hit_count: 18, hit_rate: 0.6, label: 'negative', sample_count: 30 },
  positive: { avg_forward_return: 0.022, hit_count: 35, hit_rate: 0.7, label: 'positive', sample_count: 50 },
  skipped_count: 20,
  total_signals: 100,
  window_days: 30,
};

describe('SignalBacktestView', () => {
  beforeEach(() => {
    getBacktestSummary.mockReset();
    getBacktestSummary.mockResolvedValue({ data: summary, degraded: false });
  });

  it('loads and renders overview metrics, direction hit rates and importance buckets', async () => {
    const wrapper = mount(SignalBacktestView);
    await flushPromises();

    expect(getBacktestSummary).toHaveBeenCalledWith({ market: undefined, window_days: 30, horizon: '1d' });
    expect(wrapper.find('[data-role="backtest-overview"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('100');
    expect(wrapper.text()).toContain('80');
    expect(wrapper.text()).toContain('80.0%');

    expect(wrapper.find('[data-role="backtest-directions"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('70.0%');
    expect(wrapper.text()).toContain('命中 35 / 50 样本');
    expect(wrapper.text()).toContain('命中 18 / 30 样本');

    expect(wrapper.find('[data-role="backtest-bucket-chart"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('高置信');
    expect(wrapper.text()).toContain('低置信');
  });

  it('shows the empty-buckets message when there are no evaluable samples', async () => {
    getBacktestSummary.mockResolvedValue({
      data: { ...summary, importance_buckets: [] },
      degraded: false,
    });

    const wrapper = mount(SignalBacktestView);
    await flushPromises();

    expect(wrapper.text()).toContain('当前过滤条件下暂无可评估样本');
    expect(wrapper.find('[data-role="backtest-bucket-chart"]').exists()).toBe(false);
  });

  it('shows an error message and resets metrics when the backtest API fails', async () => {
    getBacktestSummary.mockRejectedValue(new Error('回测服务不可用'));

    const wrapper = mount(SignalBacktestView);
    await flushPromises();

    expect(wrapper.find('[data-role="backtest-error"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('回测服务不可用');
    expect(wrapper.text()).toContain('候选样本');
  });

  it('reloads with the selected market when a market filter is clicked', async () => {
    const wrapper = mount(SignalBacktestView);
    await flushPromises();
    getBacktestSummary.mockClear();

    const marketButtons = wrapper.findAll('[data-role="backtest-filters"] button');
    const hkButton = marketButtons.find((b) => b.text() === '港股');
    expect(hkButton).toBeTruthy();
    await hkButton!.trigger('click');
    await flushPromises();

    expect(getBacktestSummary).toHaveBeenCalledWith({ market: 'hk', window_days: 30, horizon: '1d' });
  });

  it('reloads with the selected window when a window-days filter is clicked', async () => {
    const wrapper = mount(SignalBacktestView);
    await flushPromises();
    getBacktestSummary.mockClear();

    const filterButtons = wrapper.findAll('[data-role="backtest-filters"] button');
    const sevenDayButton = filterButtons.find((b) => b.text() === '7天');
    expect(sevenDayButton).toBeTruthy();
    await sevenDayButton!.trigger('click');
    await flushPromises();

    expect(getBacktestSummary).toHaveBeenCalledWith({ market: undefined, window_days: 7, horizon: '1d' });
  });
});
