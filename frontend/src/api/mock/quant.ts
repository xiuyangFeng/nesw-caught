import type { QuantDataStatus, QuantFundFlow, QuantRadar, QuantRecommendationLatest } from '../../types/api';

export const mockQuantLatest: QuantRecommendationLatest = {
  available: true,
  run: null,
  items: [],
  empty_reason: 'no_run_yet',
  empty_reason_detail: '尚未运行机会流水线。手动重跑将使用合成夹具，现金为合法结果。',
};

export const mockQuantDataStatus: QuantDataStatus = {
  regime: 'normal',
  coverage_pct: null,
  source_cutoff: '2026-04-10T07:30:00Z',
  dataset_version: 'synthetic-v0',
  factor_version: 'synthetic-v0',
  rule_version: 'cn-exchanges-2026-07-06',
  pit_ready: true,
  backfill_progress_pct: 0,
  note: '量化数据地基已接入独立行情库；未回填时覆盖率为 0。',
  last_run_status: null,
  daily_bar_count: 0,
  symbol_count: 0,
  fund_flow_count: 0,
  last_trade_date: null,
};

export const mockQuantFundFlow: QuantFundFlow = {
  symbol: '600519.SH',
  points: [],
  note: '尚无个股资金流。运行 make quant-backfill 后可见。',
};

export const mockQuantRadar: QuantRadar = {
  as_of: null,
  candidates: [],
  note: '事件雷达仍走合成候选；快循环尚未接入新闻主链路。',
};
