import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskStockView from './DeskStockView.vue';

const { getQuantResearch } = vi.hoisted(() => ({
  getQuantResearch: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: { getQuantResearch },
}));

const routeState = { params: { symbol: '600519.SH' } };
const push = vi.fn();

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push }),
}));

describe('DeskStockView', () => {
  beforeEach(() => {
    getQuantResearch.mockReset();
    push.mockReset();
    getQuantResearch.mockResolvedValue({
      data: {
        symbol: '600519.SH',
        modules: [
          {
            key: 'valuation',
            question: '估值情景',
            answer: '不给出无依据价格锚',
            evidence_ids: [],
            gap: 'no_financials_or_consensus',
          },
        ],
        ask_ai_context: 'ctx',
      },
      degraded: false,
    });
  });

  it('renders research modules and ask-ai affordance', async () => {
    const wrapper = mount(DeskStockView);
    await flushPromises();
    expect(wrapper.find('[data-role="desk-stock-view"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('估值情景');
    expect(wrapper.find('[data-role="desk-ask-ai"]').exists()).toBe(true);
    await wrapper.get('[data-role="desk-ask-ai"]').trigger('click');
    expect(push).toHaveBeenCalledWith({ path: '/chat', query: { desk_symbol: '600519.SH' } });
  });
});
