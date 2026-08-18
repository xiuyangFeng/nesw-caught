import type {
  QuantAiAudit,
  QuantCopilotTools,
  QuantDataStatus,
  QuantDecisionLog,
  QuantFundFlow,
  QuantPaperAccount,
  QuantProposal,
  QuantRadar,
  QuantRecommendationLatest,
  QuantRecommendationRun,
  QuantReportCard,
  QuantResearchPack,
  QuantStrategy,
} from '../../types/api';

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
  note: '快循环雷达读取 news mention；D 级传闻不会单独进入 qualified。',
};

export const mockQuantResearch: QuantResearchPack = {
  symbol: '600519.SH',
  display_name: '600519.SH',
  modules: [
    {
      key: 'valuation',
      question: '当前价格隐含什么增长',
      answer: '无一致预期时不给出无依据价格锚。',
      evidence_ids: [],
      gap: 'no_financials_or_consensus',
    },
  ],
  ask_ai_context: 'DeskContext research_pack symbol=600519.SH',
  stale: false,
};

export const mockQuantAiAudit: QuantAiAudit = {
  items: [],
  note: '未调用 LLM 时审计可为空。',
};

export const mockQuantRuns: QuantRecommendationRun[] = [];

export const mockQuantProposal: QuantProposal = {
  cash_weight: 1,
  items: [],
  note: '无合格机会时现金为 100%。LLM 不参与权重。',
};

export const mockQuantReportCard: QuantReportCard = {
  window: '30d',
  sleeves: {
    event_catalyst: { qualified: 0, watch: 0 },
    trend_flow: { qualified: 0, watch: 0 },
    fundamental_revalue: { qualified: 0, watch: 0 },
  },
  sample_size: 0,
  note: '财务未覆盖前成绩单只展示漏斗计数，不宣称超额收益。',
};

export const mockQuantStrategies: QuantStrategy[] = [];

export const mockQuantPaperAccount: QuantPaperAccount = {
  id: 1,
  cash: 1_000_000,
  initial_cash: 1_000_000,
  note: '确认后才撮合，不能用生成前价格成交。',
};

export const mockQuantDecisionLog: QuantDecisionLog = {
  items: [],
};

export const mockQuantCopilotTools: QuantCopilotTools = {
  tools: [
    'get_fund_flow',
    'get_research_snapshot',
    'search_news',
    'preview_strategy',
    'get_backtest_report',
    'get_report_card',
  ],
  note: '全部只读，副驾不能下单或改策略。',
};
