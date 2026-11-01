import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import FundFlowPanel from './FundFlowPanel.vue';

const { getFundFlow } = vi.hoisted(() => ({
  getFundFlow: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  apiClient: {
    getFundFlow,
  },
}));

describe('FundFlowPanel', () => {
  beforeEach(() => {
    getFundFlow.mockReset();
  });

  it('renders the empty fund-flow state', async () => {
    getFundFlow.mockResolvedValue({
      data: { symbol: '600519.SH', points: [], note: '东财暂无该股资金流数据。' },
      degraded: false,
    });
    const wrapper = mount(FundFlowPanel, { props: { symbol: '600519.SH' } });
    await flushPromises();

    expect(wrapper.find('[data-role="stock-fund-flow-empty"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('东财暂无该股资金流数据');
    expect(getFundFlow).toHaveBeenCalledWith('600519.SH');
  });

  it('shows the latest 10 trading days newest first with readable amounts', async () => {
    const points = Array.from({ length: 12 }, (_, index) => ({
      trade_date: `2026-10-${String(index + 1).padStart(2, '0')}`,
      main_net_inflow: index === 11 ? -526290624 : 35000,
      super_large_net: null,
      large_net: null,
      medium_net: null,
      small_net: null,
      main_net_pct: index === 11 ? -7.29 : 0.5,
    }));
    getFundFlow.mockResolvedValue({ data: { symbol: '002384.SZ', points, note: null }, degraded: false });
    const wrapper = mount(FundFlowPanel, { props: { symbol: '002384.SZ' } });
    await flushPromises();

    const rows = wrapper.findAll('[data-role="stock-fund-flow-row"]');
    expect(rows).toHaveLength(10);
    expect(rows[0].text()).toContain('2026-10-12');
    expect(rows[0].text()).toContain('-5.26亿');
    expect(rows[0].text()).toContain('-7.29%');
    expect(rows[1].text()).toContain('+3.50万');
    expect(wrapper.text()).not.toContain('2026-10-02');
  });
});
