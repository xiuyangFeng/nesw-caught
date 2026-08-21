// 量化域枚举/机器码 → 中文人话的唯一翻译层。
// 约定：所有 /desk 系列页面禁止直接把后端 reason_code/stage/gap 等机器码上屏，
// 必须经由本文件导出的映射或 tQuant 兜底函数；result_hash 只允许在运行中心出现。

export const SLEEVE_LABELS: Record<string, string> = {
  event_catalyst: '事件/催化',
  trend_flow: '趋势/资金',
  fundamental_revalue: '基本面重估',
};

export const HORIZON_LABELS: Record<string, string> = {
  '1d': '1 天',
  '5d': '5 天',
  '10d': '10 天',
  '20d': '20 天',
  '60d': '60 天',
  '120d': '120 天',
};

export const CANDIDATE_STATE_LABELS: Record<string, string> = {
  discovered: '已发现',
  validating: '验证中',
  watch: '观察池',
  qualified: '合格',
  invalidated: '已失效',
  expired: '已过期',
};

export const EVIDENCE_GRADE_LABELS: Record<string, string> = {
  A: 'A 级（强证据）',
  B: 'B 级（可靠证据）',
  C: 'C 级（弱证据）',
  D: 'D 级（传闻）',
};

export const RUN_STATUS_LABELS: Record<string, string> = {
  running: '运行中',
  ok: '正常',
  degraded: '降级',
  failed: '失败',
};

export const STAGE_LABELS: Record<string, string> = {
  data_gate: '数据闸门',
  universe_u2: '股票池筛选（U2）',
  sleeve_trend_flow: '趋势/资金打分',
  sleeve_event_catalyst: '事件/催化打分',
  sleeve_fundamental_revalue: '基本面重估打分',
  limit_up_gate: '涨跌停闸门',
  qualify: '资格裁定',
};

export const REASON_CODE_LABELS: Record<string, string> = {
  event_qualified: '事件证据过线',
  event_below_threshold_or_weak_evidence: '事件分数未过线或证据偏弱',
  trend_qualified: '主力资金与流动性过线',
  trend_liquidity_or_flow_short: '流动性或主力资金不足',
  fundamental_gap_no_financials: '财务数据未覆盖（显式缺口）',
  fundamental_below_threshold: '基本面分数未过线',
  fundamental_watch_above_threshold: '基本面过线观察（暂不晋级）',
  limit_up_open_unfillable: '开盘即涨停，不可成交',
  no_positive_edge: '今日无正期望机会',
  no_market_data: '行情库无数据，请先回填',
  market_pipeline_discovered: '进入验证',
  needs_user_confirm: '等待用户确认',
  below_min_lot: '不足 1 手（100 股），未下单',
  halted: '停牌拒单',
  no_next_bar: '无次日 K 线可成交',
  limit_up_unfilled: '涨停无法成交',
  unsupported_t_plus: '该板块 T+N 规则不支持',
  filled_t1_open: 'T+1 开盘价成交',
  no_financials: '财务/一致预期数据未采购',
};

export const GAP_LABELS: Record<string, string> = {
  no_financial_segments: '暂无财务分部数据',
  no_financial_history: '暂无财务历史数据',
  no_peer_map: '暂无可比公司映射',
  low_confidence_chain: '产业链证据置信度低',
  no_financials_or_consensus: '缺财务与一致预期数据',
  score_uncalibrated: '评分尚未校准',
  no_financials: '财务/一致预期数据未采购',
};

export const BOARD_LABELS: Record<string, string> = {
  main: '主板',
  chinext: '创业板',
  star: '科创板',
  bse: '北交所',
};

export const EMPTY_REASON_LABELS: Record<string, string> = {
  no_run_yet: '尚未运行流水线',
  no_positive_edge: '无正期望机会',
  no_market_data: '行情库无数据',
};

export const SCENARIO_LABELS: Record<string, string> = {
  real: '真实行情',
  abstain: '合成·弃权',
  mixed: '合成·混合',
};

export const TRIGGER_LABELS: Record<string, string> = {
  manual: '手动',
  scheduled: '每日自动',
};

export const PAPER_ORDER_STATUS_LABELS: Record<string, string> = {
  pending_confirm: '待确认',
  filled: '已成交',
  rejected: '已拒单',
};

export const DECISION_ACTION_LABELS: Record<string, string> = {
  paper_buy: '模拟盘买入',
  paper_sell: '模拟盘卖出',
  proposal_execute: '按组合提案下单',
};

/** 通用翻译：命中映射返回中文，未命中回退原码并告警（便于补齐映射）。 */
export function tQuant(map: Record<string, string>, code: string | null | undefined): string {
  if (code == null || code === '') return '—';
  const label = map[code];
  if (label) return label;
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.warn(`[quantLabels] 未映射的机器码：${code}`);
  }
  return code;
}

/** sleeveLabel 等单键便捷别名（视图里高频使用）。 */
export const sleeveLabel = (code: string | null | undefined): string => tQuant(SLEEVE_LABELS, code);
export const reasonLabel = (code: string | null | undefined): string => tQuant(REASON_CODE_LABELS, code);
export const stateLabel = (code: string | null | undefined): string => tQuant(CANDIDATE_STATE_LABELS, code);
export const gradeLabel = (code: string | null | undefined): string => tQuant(EVIDENCE_GRADE_LABELS, code);
export const runStatusLabel = (code: string | null | undefined): string => tQuant(RUN_STATUS_LABELS, code);
export const stageLabel = (code: string | null | undefined): string => tQuant(STAGE_LABELS, code);
export const gapLabel = (code: string | null | undefined): string => tQuant(GAP_LABELS, code);
