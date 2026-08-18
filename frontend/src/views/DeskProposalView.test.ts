import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskProposalView from './DeskProposalView.vue';

const { getQuantProposal } = vi.hoisted(() => ({ getQuantProposal: vi.fn() }));

vi.mock('../api/client', () => ({
  apiClient: { getQuantProposal },
}));

vi.mock('vue-router', () => ({
  RouterLink: { props: ['to'], template: '<a :href="typeof to === \'string\' ? to : to.path"><slot /></a>' },
}));

describe('DeskProposalView', () => {
  beforeEach(() => {
    getQuantProposal.mockResolvedValue({
      data: { cash_weight: 1, items: [], note: '无合格机会时现金为 100%。LLM 不参与权重。' },
      degraded: false,
    });
  });

  it('renders cash as the default allocation', async () => {
    const wrapper = mount(DeskProposalView);
    await flushPromises();
    expect(wrapper.find('[data-role="desk-proposal-view"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="desk-proposal-cash"]').text()).toContain('现金 100%');
    expect(wrapper.text()).toContain('LLM 不参与权重');
  });
});
