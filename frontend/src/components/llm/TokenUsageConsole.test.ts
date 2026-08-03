import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import TokenUsageConsole from './TokenUsageConsole.vue';
import type { TokenStats } from './types';

const stats: TokenStats = {
  overall: {
    prompt_tokens: 8_050,
    completion_tokens: 9_230,
    total_tokens: 17_280,
    cost_usd: 9.391,
    cost_available: true,
  },
  models: [
    {
      model_name: 'secondary-model',
      prompt_tokens: 100,
      completion_tokens: 200,
      total_tokens: 300,
      call_count: 2,
      cost_usd: 0.2,
      cost_available: true,
    },
    {
      model_name: 'deepseek-v4-flash',
      prompt_tokens: 7_950,
      completion_tokens: 9_030,
      total_tokens: 16_980,
      call_count: 28,
      cost_usd: 9.191,
      cost_available: true,
    },
  ],
  operations: [
    { operation_type: 'chat', total_tokens: 14_000 },
    { operation_type: 'translate', total_tokens: 3_280 },
  ],
  daily: [
    { date: '2026-08-02', prompt_tokens: 8_050, completion_tokens: 9_230, total_tokens: 17_280 },
  ],
  budget: {
    month: '2026-08',
    month_cost_usd: 9.391,
    monthly_budget_usd: 20,
    budget_available: true,
    over_budget: false,
    usage_ratio: 0.47,
  },
};

describe('TokenUsageConsole', () => {
  it('renders a compact ledger with actual top-model ranking and token composition', () => {
    const wrapper = mount(TokenUsageConsole, { props: { stats, loading: false } });

    expect(wrapper.find('[data-role="usage-metric-strip"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('17,280');
    expect(wrapper.text()).toContain('$9.3910');
    expect(wrapper.text()).toContain('30');

    const ranking = wrapper.get('[data-role="model-usage-ranking"]');
    expect(ranking.findAll('[data-role="model-usage-row"]')).toHaveLength(2);
    expect(ranking.findAll('[data-role="model-usage-row"]')[0].text()).toContain('deepseek-v4-flash');
    expect(ranking.text()).toContain('98%');
    expect(wrapper.find('[data-role="token-budget-track"]').exists()).toBe(true);
  });

  it('emits refresh from the compact console action', async () => {
    const wrapper = mount(TokenUsageConsole, { props: { stats, loading: false } });

    await wrapper.get('[data-role="refresh-token-usage"]').trigger('click');

    expect(wrapper.emitted('refresh')).toHaveLength(1);
  });
});
