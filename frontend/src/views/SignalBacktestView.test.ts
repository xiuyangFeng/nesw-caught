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

  it('does not render phase 2 sections (excess return, score buckets, calibration) when the backend has not run the new backtest yet', async () => {
    const wrapper = mount(SignalBacktestView);
    await flushPromises();

    expect(wrapper.find('[data-role="backtest-excess-return"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="backtest-score-buckets"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="backtest-calibration"]').exists()).toBe(false);
  });

  it('renders the phase 2 additive fields (excess return, per-news hit rate, score buckets, calibration) when present', async () => {
    const phase2Summary: BacktestSummary = {
      ...summary,
      avg_excess_return: 0.012,
      benchmark_note: '未找到市场基准指数快照，已使用同窗口内全部可评样本的平均前视收益作为代理基准。',
      distinct_news_count: 64,
      per_news_hit_rate: 0.66,
      skipped_stale_count: 5,
      score_buckets: [
        { range_label: '0.0-0.2', sample_count: 40, hit_rate: 0.5, avg_forward_return: 0.001, avg_excess_return: -0.002 },
        { range_label: '0.6-0.8', sample_count: 15, hit_rate: 0.73, avg_forward_return: 0.03, avg_excess_return: 0.018 },
      ],
      calibration: {
        generated_at: '2026-08-02T00:00:00Z',
        horizon: '1d',
        mapping: [
          { score_min: 0, score_max: 0.2, sample_count: 40, hit_rate: 0.5, calibrated_confidence: 0.5, low_sample: false },
          { score_min: 0.8, score_max: 1, sample_count: 8, hit_rate: 0.75, calibrated_confidence: 0.75, low_sample: true },
        ],
        suggested_positive_threshold: 0.6,
        suggested_negative_threshold: -0.6,
        window_days: 30,
      },
    };
    getBacktestSummary.mockResolvedValue({ data: phase2Summary, degraded: false });

    const wrapper = mount(SignalBacktestView);
    await flushPromises();

    expect(wrapper.find('[data-role="backtest-excess-return"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('+1.20%');
    expect(wrapper.text()).toContain('未找到市场基准指数快照');
    expect(wrapper.text()).toContain('去重新闻数');
    expect(wrapper.text()).toContain('64');
    expect(wrapper.text()).toContain('按新闻加权命中率');
    expect(wrapper.text()).toContain('陈旧快照跳过');

    const bucketsTable = wrapper.find('[data-role="backtest-score-buckets-table"]');
    expect(bucketsTable.exists()).toBe(true);
    expect(bucketsTable.text()).toContain('0.0-0.2');
    expect(bucketsTable.text()).toContain('0.6-0.8');

    const calibrationTable = wrapper.find('[data-role="backtest-calibration-table"]');
    expect(calibrationTable.exists()).toBe(true);
    const rows = calibrationTable.findAll('tbody tr');
    expect(rows).toHaveLength(2);
    expect(rows[1].attributes('data-low-sample')).toBe('true');
    expect(rows[1].classes()).toContain('opacity-40');
    expect(rows[0].attributes('data-low-sample')).toBe('false');

    expect(wrapper.find('[data-role="backtest-calibration-thresholds"]').text()).toContain('0.60');
  });
});
