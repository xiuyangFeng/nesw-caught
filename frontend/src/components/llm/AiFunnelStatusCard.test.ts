import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { AiFunnelStatus } from '../../types/api';

const { getAiFunnelStatus } = vi.hoisted(() => ({
  getAiFunnelStatus: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  apiClient: { getAiFunnelStatus },
}));

import AiFunnelStatusCard from './AiFunnelStatusCard.vue';

function buildStatus(overrides: Partial<AiFunnelStatus> = {}): AiFunnelStatus {
  return {
    enabled: true,
    active: true,
    inactive_reason: null,
    model_name: 'gpt-6.1-terra',
    model_display_name: 'Terra 中转',
    today: {
      screened: 812,
      screen_errors: 3,
      analyzed: 46,
      analysis_errors: 1,
      impacts: 97,
      analysis_daily_limit: 300,
      cost_usd: 0.12345,
    },
    usage: [
      { operation_type: 'ai_impact', calls: 47, prompt_tokens: 120000, completion_tokens: 30000, cost_usd: 0.0405 },
      { operation_type: 'ai_screen', calls: 41, prompt_tokens: 250000, completion_tokens: 40000, cost_usd: 0.0675 },
    ],
    month_cost_usd: 2.5,
    monthly_budget_usd: 20,
    over_budget: false,
    last_error: { message: 'timeout after 60s', at: '2026-11-01T02:30:00Z' },
    ...overrides,
  };
}

async function mountCard(status: AiFunnelStatus) {
  getAiFunnelStatus.mockResolvedValue({ data: status, degraded: false });
  const wrapper = mount(AiFunnelStatusCard);
  await flushPromises();
  return wrapper;
}

describe('AiFunnelStatusCard', () => {
  beforeEach(() => {
    getAiFunnelStatus.mockReset();
  });

  it('shows online state, model, today counts, costs and usage rows', async () => {
    const wrapper = await mountCard(buildStatus());

    expect(wrapper.get('[data-role="ai-funnel-state"]').text()).toContain('在线');
    expect(wrapper.find('[data-role="ai-funnel-reason"]').exists()).toBe(false);
    expect(wrapper.get('[data-role="ai-funnel-model"]').text()).toBe('Terra 中转（gpt-6.1-terra）');

    const today = wrapper.get('[data-role="ai-funnel-today"]').text();
    expect(today).toContain('粗筛 812（失败 3）');
    expect(today).toContain('精读 46 / 300（失败 1）');
    expect(today).toContain('影响 97');
    expect(today).toContain('今日费用 $0.1235');
    expect(wrapper.get('[data-role="ai-funnel-month"]').text()).toMatch(/本月 \$2\.5000 \/ 预算\s*\$20\.00/);

    const rows = wrapper.findAll('[data-role="ai-funnel-usage-row"]');
    expect(rows).toHaveLength(3);
    expect(rows[0].text()).toContain('粗筛');
    expect(rows[0].text()).toContain('41');
    expect(rows[0].text()).toContain('250,000');
    expect(rows[1].text()).toContain('精读');
    expect(rows[1].text()).toContain('$0.0405');
    expect(rows[2].text()).toContain('板块推断');

    expect(wrapper.get('[data-role="ai-funnel-last-error"]').text()).toContain('timeout after 60s');
  });

  it.each([
    ['disabled', '漏斗已关闭（AI_FUNNEL_ENABLED=false）'],
    ['no_default_model', '未设置默认模型：在下方添加 gpt-6.1-terra 并设为默认'],
    ['over_budget', '本月费用已达预算，已暂停'],
    ['worker_not_running', '漏斗 worker 未运行'],
  ] as const)('shows the inactive reason text for %s', async (reason, text) => {
    const wrapper = await mountCard(
      buildStatus({ active: false, inactive_reason: reason, model_name: null, model_display_name: null, last_error: null }),
    );

    expect(wrapper.get('[data-role="ai-funnel-state"]').text()).toContain('未运行');
    expect(wrapper.get('[data-role="ai-funnel-reason"]').text()).toBe(text);
    expect(wrapper.get('[data-role="ai-funnel-model"]').text()).toBe('未设置');
    expect(wrapper.find('[data-role="ai-funnel-last-error"]').exists()).toBe(false);
  });

  it('shows a load error', async () => {
    getAiFunnelStatus.mockRejectedValue(new Error('backend offline'));
    const wrapper = mount(AiFunnelStatusCard);
    await flushPromises();

    expect(wrapper.get('[data-role="ai-funnel-error"]').text()).toContain('backend offline');
  });
});
