import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskBacktestView from './DeskBacktestView.vue';

const { runQuantBacktest } = vi.hoisted(() => ({ runQuantBacktest: vi.fn() }));

vi.mock('../api/client', () => ({
  apiClient: { runQuantBacktest },
}));

describe('DeskBacktestView', () => {
  beforeEach(() => {
    runQuantBacktest.mockResolvedValue({
      data: {
        id: 1,
        status: 'completed',
        exploratory: true,
        qualified: false,
        metrics: { n: 2 },
        note: '探索性回测：退市股未补齐，不得显示 qualified。',
      },
      degraded: false,
    });
  });

  it('runs an exploratory backtest that cannot be qualified', async () => {
    const wrapper = mount(DeskBacktestView);
    await wrapper.get('[data-role="desk-backtest-run"]').trigger('click');
    await flushPromises();
    expect(runQuantBacktest).toHaveBeenCalled();
    expect(wrapper.get('[data-role="desk-backtest-report"]').text()).toContain('qualified 否');
    expect(wrapper.text()).toContain('探索性');
  });
});
