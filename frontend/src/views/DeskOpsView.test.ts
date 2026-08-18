import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskOpsView from './DeskOpsView.vue';

const { getQuantDataStatus, getQuantAiAudit, getQuantRuns, getQuantDecisionLog } = vi.hoisted(() => ({
  getQuantDataStatus: vi.fn(),
  getQuantAiAudit: vi.fn(),
  getQuantRuns: vi.fn(),
  getQuantDecisionLog: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: {
    getQuantDataStatus,
    getQuantAiAudit,
    getQuantRuns,
    getQuantDecisionLog,
  },
}));

describe('DeskOpsView', () => {
  beforeEach(() => {
    getQuantAiAudit.mockReset();
    getQuantRuns.mockReset();
    getQuantDecisionLog.mockReset();
    getQuantAiAudit.mockResolvedValue({ data: { items: [], note: '暂无调用记录。' }, degraded: false });
    getQuantRuns.mockResolvedValue({ data: [], degraded: false });
    getQuantDecisionLog.mockResolvedValue({ data: { items: [] }, degraded: false });
    getQuantDataStatus.mockResolvedValue({
      data: {
        regime: 'normal',
        coverage_pct: 0,
        dataset_version: 'synthetic-v0',
        factor_version: 'synthetic-v0',
        rule_version: 'cn-exchanges-2026-07-06',
        pit_ready: true,
        backfill_progress_pct: 0,
        note: '量化数据地基已接入独立行情库；未回填时覆盖率为 0。',
        daily_bar_count: 0,
        symbol_count: 0,
        fund_flow_count: 0,
        last_trade_date: null,
      },
      degraded: false,
    });
  });

  it('renders the data health tab with coverage gauges', async () => {
    const wrapper = mount(DeskOpsView);
    await flushPromises();

    expect(wrapper.find('[data-role="desk-ops-view"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="desk-ops-data-health"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('日线条数');
    expect(wrapper.text()).toContain('独立行情库');
  });

  it('renders the AI audit tab', async () => {
    const wrapper = mount(DeskOpsView);
    await flushPromises();
    await wrapper.get('[data-role="desk-ops-tab-ai"]').trigger('click');
    expect(wrapper.find('[data-role="desk-ops-ai-audit"]').exists()).toBe(true);
  });

  it('renders pipeline runs and decision log tabs', async () => {
    const wrapper = mount(DeskOpsView);
    await flushPromises();
    await wrapper.get('[data-role="desk-ops-tab-runs"]').trigger('click');
    expect(wrapper.find('[data-role="desk-ops-runs"]').exists()).toBe(true);
    await wrapper.get('[data-role="desk-ops-tab-decisions"]').trigger('click');
    expect(wrapper.find('[data-role="desk-ops-decisions"]').exists()).toBe(true);
  });
});
