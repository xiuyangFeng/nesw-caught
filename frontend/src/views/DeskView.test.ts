import { flushPromises, mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { QuantDataStatus, QuantRadar, QuantRecommendationLatest } from '../types/api';
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
  proposal: { cash_weight: 1, items: [], note: '无合格机会时现金为 100%。LLM 不参与权重。' },
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
    deskStore.loading = false;
    deskStore.running = false;
    deskStore.error = null;
    deskStore.usingMock = false;
    deskStore.qualifiedItems = [];
    deskStore.watchItems = [];
    deskStore.isDegraded = false;
    deskStore.hasQualified = false;
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

  it('triggers a manual rerun', async () => {
    const wrapper = mount(DeskView);
    await flushPromises();

    await wrapper.get('[data-role="desk-rerun"]').trigger('click');
    await flushPromises();

    expect(deskStore.rerun).toHaveBeenCalledWith('abstain');
  });
});
