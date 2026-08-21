import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskBacktestView from './DeskBacktestView.vue';

const { runQuantBacktest, getQuantFactors, getQuantStrategies } = vi.hoisted(() => ({
  runQuantBacktest: vi.fn(),
  getQuantFactors: vi.fn(),
  getQuantStrategies: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: { runQuantBacktest, getQuantFactors, getQuantStrategies },
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}));

const report = {
  id: 1,
  status: 'completed',
  exploratory: true,
  qualified: false,
  symbol: '600519.SH',
  bars_used: 130,
  equity_curve: [
    { date: '2026-01-05', equity: 1 },
    { date: '2026-04-10', equity: 1.08 },
  ],
  trades: [
    {
      signal_date: '2026-01-05',
      entry_date: '2026-01-06',
      entry_price: 10.5,
      exit_date: '2026-04-10',
      exit_price: 11.3,
      pnl: 0.0762,
    },
  ],
  coverage_error: null,
  metrics: { net_return: 0.08, max_drawdown: 0.03, trades: 1, unfilled: 0 },
  note: '探索性回测：真实日线驱动；退市股未补齐，不得显示 qualified。',
};

describe('DeskBacktestView', () => {
  beforeEach(() => {
    runQuantBacktest.mockReset();
    getQuantFactors.mockReset();
    getQuantStrategies.mockReset();
    runQuantBacktest.mockResolvedValue({ data: report, degraded: false });
    getQuantFactors.mockResolvedValue({
      data: [{ key: 'main_inflow_1d', sleeve: 'trend_flow', horizon: '5d' }],
      degraded: false,
    });
    getQuantStrategies.mockResolvedValue({ data: [], degraded: false });
  });

  it('runs a real backtest for a symbol and renders the graphical report', async () => {
    const wrapper = mount(DeskBacktestView);
    await flushPromises();

    await wrapper.get('[data-role="desk-backtest-symbol"]').setValue('600519.SH');
    await wrapper.get('[data-role="desk-backtest-run"]').trigger('click');
    await flushPromises();

    expect(runQuantBacktest).toHaveBeenCalled();
    const payload = runQuantBacktest.mock.calls[0][0];
    expect(payload.symbol).toBe('600519.SH');
    expect(payload.dsl.sleeve).toBe('trend_flow');

    // 图形化报告：指标卡片 + 净值曲线 + 交易明细，而不是 JSON <pre>
    const reportCard = wrapper.get('[data-role="desk-backtest-report"]');
    expect(reportCard.text()).toContain('8.00%');
    expect(reportCard.text()).toContain('130');
    expect(wrapper.find('[data-role="equity-curve-line"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="desk-backtest-trades"]').text()).toContain('10.50');
    expect(wrapper.find('pre').exists()).toBe(false);
    expect(reportCard.text()).toContain('不得晋级');
  });

  it('requires a symbol before running', async () => {
    const wrapper = mount(DeskBacktestView);
    await flushPromises();

    await wrapper.get('[data-role="desk-backtest-run"]').trigger('click');
    await flushPromises();

    expect(runQuantBacktest).not.toHaveBeenCalled();
    expect(wrapper.get('[data-role="desk-backtest-error"]').text()).toContain('标的代码');
  });

  it('shows the coverage error card instead of a report when data is insufficient', async () => {
    runQuantBacktest.mockResolvedValue({
      data: { ...report, coverage_error: '600519.SH 在选定区间内仅有 3 根日线（需 ≥60），请先回填。', trades: [], equity_curve: [] },
      degraded: false,
    });
    const wrapper = mount(DeskBacktestView);
    await flushPromises();

    await wrapper.get('[data-role="desk-backtest-symbol"]').setValue('600519.SH');
    await wrapper.get('[data-role="desk-backtest-run"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-role="desk-backtest-coverage"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="desk-backtest-coverage"]').text()).toContain('回填');
    expect(wrapper.find('[data-role="desk-backtest-report"]').exists()).toBe(false);
  });

  it('uses the structured strategy builder instead of a raw JSON textarea', async () => {
    const wrapper = mount(DeskBacktestView);
    await flushPromises();

    expect(wrapper.find('[data-role="strategy-builder-root"]').exists()).toBe(true);
    expect(wrapper.findAll('[data-role="strategy-builder-row"]')).toHaveLength(1);
  });
});
