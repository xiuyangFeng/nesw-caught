import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import FundFlowPanel from './FundFlowPanel.vue';

const { getQuantFundFlow } = vi.hoisted(() => ({
  getQuantFundFlow: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  apiClient: {
    getQuantFundFlow,
  },
}));

describe('FundFlowPanel', () => {
  beforeEach(() => {
    getQuantFundFlow.mockReset();
  });

  it('renders the empty fund-flow state', async () => {
    getQuantFundFlow.mockResolvedValue({
      data: { symbol: '600519.SH', points: [], note: '尚无个股资金流。运行 make quant-backfill 后可见。' },
      degraded: false,
    });
    const wrapper = mount(FundFlowPanel, { props: { symbol: '600519.SH' } });
    await flushPromises();

    expect(wrapper.find('[data-role="stock-fund-flow-empty"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('尚无个股资金流');
    expect(getQuantFundFlow).toHaveBeenCalledWith('600519.SH');
  });
});
