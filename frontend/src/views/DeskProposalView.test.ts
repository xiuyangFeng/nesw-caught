import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskProposalView from './DeskProposalView.vue';

const { getQuantProposal, executeQuantProposal } = vi.hoisted(() => ({
  getQuantProposal: vi.fn(),
  executeQuantProposal: vi.fn(),
}));

const routerMock = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock('../api/client', () => ({
  apiClient: { getQuantProposal, executeQuantProposal },
}));

vi.mock('vue-router', () => ({
  useRouter: () => routerMock,
  RouterLink: { props: ['to'], template: '<a :href="typeof to === \'string\' ? to : to.path"><slot /></a>' },
}));

const proposal = {
  cash_weight: 0.4,
  items: [
    { symbol: '000001.SZ', sleeve: 'trend_flow', weight: 0.2, reject_reason: null },
    { symbol: '600519.SH', sleeve: 'trend_flow', weight: 0.2, reject_reason: null },
    { symbol: '300750.SZ', sleeve: 'trend_flow', weight: 0.2, reject_reason: null },
  ],
  note: 'LLM 不参与权重。',
};

const executeResult = {
  cash_weight: 0.4,
  orders: [
    { symbol: '000001.SZ', sleeve: 'trend_flow', weight: 0.2, shares: 400, filled: true, fill_price: 10.5, reject_reason: null },
    { symbol: '600519.SH', sleeve: 'trend_flow', weight: 0.2, shares: 0, filled: false, fill_price: null, reject_reason: 'below_min_lot' },
  ],
};

describe('DeskProposalView', () => {
  beforeEach(() => {
    getQuantProposal.mockReset();
    executeQuantProposal.mockReset();
    routerMock.push.mockClear();
    getQuantProposal.mockResolvedValue({ data: proposal, degraded: false });
    executeQuantProposal.mockResolvedValue({ data: executeResult, degraded: false });
  });

  it('renders cash as the default allocation when there are no positions', async () => {
    getQuantProposal.mockResolvedValue({
      data: { cash_weight: 1, items: [], note: '无合格机会时现金为 100%。LLM 不参与权重。' },
      degraded: false,
    });
    const wrapper = mount(DeskProposalView);
    await flushPromises();
    expect(wrapper.find('[data-role="desk-proposal-view"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="desk-proposal-cash"]').text()).toContain('现金 100%');
    expect(wrapper.text()).toContain('LLM 不参与权重');
    expect(wrapper.find('[data-role="desk-proposal-execute"]').exists()).toBe(false);
  });

  it('renders positions with translated sleeve labels', async () => {
    const wrapper = mount(DeskProposalView);
    await flushPromises();
    expect(wrapper.findAll('[data-role="desk-proposal-items"] tbody tr')).toHaveLength(3);
    expect(wrapper.text()).toContain('趋势/资金');
  });

  it('opens a confirm dialog and executes the proposal into the paper account', async () => {
    const wrapper = mount(DeskProposalView);
    await flushPromises();

    await wrapper.get('[data-role="desk-proposal-execute"]').trigger('click');
    expect(wrapper.find('[data-role="desk-proposal-confirm"]').exists()).toBe(true);
    expect(wrapper.findAll('[data-role="desk-proposal-confirm-list"] li')).toHaveLength(3);

    await wrapper.get('[data-role="desk-proposal-confirm-ok"]').trigger('click');
    await flushPromises();

    expect(executeQuantProposal).toHaveBeenCalled();
    expect(wrapper.find('[data-role="desk-proposal-confirm"]').exists()).toBe(false);
    const list = wrapper.get('[data-role="desk-proposal-execute-list"]');
    expect(list.text()).toContain('成交 400 股 @ 10.50');
    expect(list.text()).toContain('未成交');
  });

  it('cancels the confirm dialog without executing', async () => {
    const wrapper = mount(DeskProposalView);
    await flushPromises();

    await wrapper.get('[data-role="desk-proposal-execute"]').trigger('click');
    await wrapper.get('[data-role="desk-proposal-confirm-cancel"]').trigger('click');

    expect(executeQuantProposal).not.toHaveBeenCalled();
    expect(wrapper.find('[data-role="desk-proposal-confirm"]').exists()).toBe(false);
  });
});
