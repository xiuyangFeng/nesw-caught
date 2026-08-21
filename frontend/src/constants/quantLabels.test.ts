import { describe, expect, it } from 'vitest';

import {
  CANDIDATE_STATE_LABELS,
  EVIDENCE_GRADE_LABELS,
  GAP_LABELS,
  REASON_CODE_LABELS,
  RUN_STATUS_LABELS,
  SLEEVE_LABELS,
  STAGE_LABELS,
  gapLabel,
  reasonLabel,
  runStatusLabel,
  sleeveLabel,
  stateLabel,
  tQuant,
} from './quantLabels';

describe('quantLabels', () => {
  it('covers every backend sleeve/state/status/stage/gap/reason code used by the desk', () => {
    // 后端实际会出现在前端的机器码全集：新增枚举时必须补映射，否则 tQuant 回退原码。
    const sleeves = ['event_catalyst', 'trend_flow', 'fundamental_revalue'];
    const states = ['discovered', 'validating', 'watch', 'qualified', 'invalidated', 'expired'];
    const runStatuses = ['running', 'ok', 'degraded', 'failed'];
    const stages = [
      'data_gate',
      'universe_u2',
      'sleeve_trend_flow',
      'sleeve_event_catalyst',
      'sleeve_fundamental_revalue',
      'limit_up_gate',
      'qualify',
    ];
    const gaps = [
      'no_financial_segments',
      'no_financial_history',
      'no_peer_map',
      'low_confidence_chain',
      'no_financials_or_consensus',
      'score_uncalibrated',
      'no_financials',
    ];
    const reasons = [
      'event_qualified',
      'event_below_threshold_or_weak_evidence',
      'trend_qualified',
      'trend_liquidity_or_flow_short',
      'fundamental_gap_no_financials',
       'fundamental_below_threshold',
      'fundamental_watch_above_threshold',
      'limit_up_open_unfillable',
      'no_positive_edge',
      'no_market_data',
       'needs_user_confirm',
      'below_min_lot',
      'halted',
      'no_next_bar',
      'limit_up_unfilled',
      'unsupported_t_plus',
      'filled_t1_open',
    ];

    expect(sleeves.every((code) => SLEEVE_LABELS[code])).toBe(true);
    expect(states.every((code) => CANDIDATE_STATE_LABELS[code])).toBe(true);
    expect(runStatuses.every((code) => RUN_STATUS_LABELS[code])).toBe(true);
    expect(stages.every((code) => STAGE_LABELS[code])).toBe(true);
    expect(gaps.every((code) => GAP_LABELS[code])).toBe(true);
    expect(reasons.every((code) => REASON_CODE_LABELS[code])).toBe(true);
    expect(['A', 'B', 'C', 'D'].every((grade) => EVIDENCE_GRADE_LABELS[grade])).toBe(true);
  });

  it('translates known codes to Chinese', () => {
    expect(sleeveLabel('trend_flow')).toBe('趋势/资金');
    expect(stateLabel('qualified')).toBe('合格');
    expect(reasonLabel('limit_up_open_unfillable')).toBe('开盘即涨停，不可成交');
    expect(runStatusLabel('degraded')).toBe('降级');
    expect(gapLabel('no_financials')).toBe('财务/一致预期数据未采购');
  });

  it('falls back to the raw code with a dash for unknown or empty values', () => {
    expect(tQuant(SLEEVE_LABELS, 'never_seen_code')).toBe('never_seen_code');
    expect(tQuant(SLEEVE_LABELS, null)).toBe('—');
    expect(tQuant(SLEEVE_LABELS, '')).toBe('—');
  });
});
