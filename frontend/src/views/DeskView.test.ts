import { flushPromises, mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { QuantDataStatus, QuantProposal, QuantRadar, QuantRecommendationLatest } from '../types/api';
import DeskView from './DeskView.vue';

const latest: QuantRecommendationLatest = {
  available: true,
  run: null,
  items: [],
  empty_reason: 'no_positive_edge',
  empty_reason_detail: '今日无正期望机会：阈值、流动性或信息可得时间未过线，现金为合法结果。',
};

const dataStatus: QuantDataStatus = {
  regime: 'normal',
  coverage_pct: null,
  source_cutoff: '2026-04-10T07:30:00Z',
  dataset_version: 'synthetic-v0',
  factor_version: 'synthetic-v0',
  rule_version: 'cn-exchanges-2026-07-06',
  pit_ready: true,
  backfill_progress_pct: 0,
  note: '量化数据地基已接入独立行情库；未回填时覆盖率为 0。',
  last_run_status: 'ok',
  daily_bar_count: 0,
  symbol_count: 0,
  fund_flow_count: 0,
  last_trade_date: null,
};

const radar: QuantRadar = {
  as_of: null,
  candidates: [],
  note: 'Phase 0 合成事件雷达，快循环尚未接入新闻主链路。',
};

const proposal: QuantProposal = {
  cash_weight: 1,
  items: [],
  note: '无合格机会时现金为 100%。LLM 不参与权重。',
};

const deskStore = reactive({
  latest,
  dataStatus,
  radar,
  loading: false,
  running: false,
  error: null as string | null,
  usingMock: false,
  qualifiedItems: [] as QuantRecommendationLatest['items'],
  watchItems: [] as QuantRecommendationLatest['items'],
  isDegraded: false,
  hasQualified: false,
  proposal,
  sleeveCounts: {
    event_catalyst: { qualified: 0, watch: 0, total: 0 },
    trend_flow: { qualified: 0, watch: 0, total: 0 },
    fundamental_revalue: { qualified: 0, watch: 0, total: 0 },
  },
  loadDesk: vi.fn(async () => undefined),
  rerun: vi.fn(async () => undefined),
});

vi.mock('../stores/deskStore', () => ({
  useDeskStore: () => deskStore,
}));

vi.mock('vue-router', () => ({
  RouterLink: {
    props: ['to'],
    template: '<a :href="typeof to === \'string\' ? to : to.path"><slot /></a>',
  },
}));

describe('DeskView', () => {
  beforeEach(() => {
    deskStore.latest = latest;
    deskStore.dataStatus = dataStatus;
    deskStore.radar = radar;
    deskStore.proposal = proposal;
    deskStore.loading = false;
    deskStore.running = false;
    deskStore.error = null;
    deskStore.usingMock = false;
    deskStore.qualifiedItems = [];
    deskStore.watchItems = [];
    deskStore.isDegraded = false;
    deskStore.hasQualified = false;
    deskStore.sleeveCounts = {
      event_catalyst: { qualified: 0, watch: 0, total: 0 },
      trend_flow: { qualified: 0, watch: 0, total: 0 },
      fundamental_revalue: { qualified: 0, watch: 0, total: 0 },
    };
    deskStore.loadDesk.mockClear();
    deskStore.rerun.mockClear();
  });

  it('renders the empty opportunity state as a first-class result', async () => {
    const wrapper = mount(DeskView);
    await flushPromises();

    expect(deskStore.loadDesk).toHaveBeenCalled();
    expect(wrapper.find('[data-role="desk-view"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="desk-empty"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('今日无正期望机会');
    expect(wrapper.text()).toContain('现金为合法结果');
  });

  it('shows a degraded banner when the run is degraded', async () => {
    deskStore.isDegraded = true;
    const wrapper = mount(DeskView);
    await flushPromises();

    expect(wrapper.find('[data-role="desk-degraded-banner"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('降级');
  });

  it('triggers a manual rerun against real market data by default', async () => {
    const wrapper = mount(DeskView);
    await flushPromises();

    await wrapper.get('[data-role="desk-rerun"]').trigger('click');
    await flushPromises();

    expect(deskStore.rerun).toHaveBeenCalledWith('real');
  });

  it('renders the dashboard section with a legal cash-only empty state', async () => {
    const wrapper = mount(DeskView);
    await flushPromises();

    expect(wrapper.find('[data-role="desk-dashboard"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="desk-dashboard-coverage"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="desk-dashboard-funnel"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="desk-dashboard-run"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="desk-dashboard-proposal"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="desk-dashboard-proposal-empty"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="desk-dashboard-proposal-empty"]').text()).toContain('现金 100%');
  });

  it('renders populated dashboard metrics: coverage bar, sleeve funnel, run badge and proposal bars', async () => {
    deskStore.dataStatus = {
      ...dataStatus,
      coverage_pct: 62,
      symbol_count: 4200,
      daily_bar_count: 980000,
      last_trade_date: '2026-08-17',
      last_run_status: 'ok',
    };
    deskStore.sleeveCounts = {
      event_catalyst: { qualified: 1, watch: 3, total: 4 },
      trend_flow: { qualified: 2, watch: 1, total: 3 },
      fundamental_revalue: { qualified: 0, watch: 0, total: 0 },
    };
    deskStore.latest = {
      ...latest,
      run: {
        id: 1,
        run_date: '2026-08-18',
        scenario: 'real',
        trigger: 'manual',
        status: 'ok',
        started_at: '2026-08-18T01:00:00Z',
        finished_at: '2026-08-18T01:02:00Z',
        result_hash: 'abcdef1234567890',
        dataset_version: 'real-v1',
        factor_version: 'real-v1',
        rule_version: 'cn-exchanges-2026-07-06',
        code_commit: 'deadbeef',
        source_cutoff: '2026-08-18T01:00:00Z',
      },
    };
    deskStore.proposal = {
      cash_weight: 0.92,
      items: [{ symbol: '600519.SH', sleeve: 'trend_flow', weight: 0.08, reject_reason: null }],
      note: '单票 8%，其余现金。',
    };

    const wrapper = mount(DeskView);
    await flushPromises();

    expect(wrapper.get('[data-role="desk-dashboard-coverage-bar"]').attributes('style')).toContain('width: 62%');
    expect(wrapper.get('[data-role="desk-dashboard-funnel"]').text()).toContain('合格 2 · 观察 1');
    expect(wrapper.get('[data-role="desk-dashboard-run-badge"]').text()).toContain('正常');
    expect(wrapper.get('[data-role="desk-dashboard-proposal"]').text()).toContain('600519.SH');
    expect(wrapper.get('[data-role="desk-dashboard-proposal"]').text()).toContain('8%');
    expect(wrapper.get('[data-role="desk-dashboard-proposal"]').text()).toContain('92%');
  });
});
