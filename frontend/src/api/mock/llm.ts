// LLM 域 mock 数据：大模型接入配置、翻译、新闻个股映射分析(NewsAnalysis)，
// 自选股 AI 投研简报文本(WatchlistAiInsight)，以及 Token 用量统计(LLMStats)。

import type { LLMConfigSummary, LLMStats, LLMTranslateResponse, NewsAnalysis, WatchlistAiInsight } from '../../types/api';
import { isoMinutesAgo } from './shared';

export const mockLlmConfig: LLMConfigSummary = {
  configured: true,
  id: 1,
  provider_name: 'openai_compatible',
  display_name: 'OpenAI Compatible',
  model_name: 'deepseek-chat',
  base_url: 'https://example-llm.test/v1',
  api_key_set: true,
  is_active: true,
  is_default: true,
  updated_at: isoMinutesAgo(5),
};

export const mockLlmConfigs: LLMConfigSummary[] = [
  { ...mockLlmConfig }
];

export const buildMockTranslation = (text: string): LLMTranslateResponse => ({
  provider_name: mockLlmConfig.provider_name ?? 'openai_compatible',
  model_name: mockLlmConfig.model_name ?? 'deepseek-chat',
  translated_text: `模拟翻译：${text}`,
});

export const mockNewsAnalyses: Record<number, NewsAnalysis> = {
  101: {
    news_id: 101,
    provider_name: 'openai_compatible',
    model_name: 'deepseek-chat',
    analysis_status: 'success',
    top_pick: {
      symbol: '0700.HK',
      market: 'hk',
      company_name: 'Tencent',
      confidence: 0.91,
      reason: '企业 AI 代理产品扩张最直接映射到腾讯云与企业软件叙事。',
    },
    candidates: [
      {
        symbol: '0700.HK',
        market: 'hk',
        company_name: 'Tencent',
        confidence: 0.91,
        reason: '企业 AI 代理产品扩张最直接映射到腾讯云与企业软件叙事。',
      },
      {
        symbol: '9988.HK',
        market: 'hk',
        company_name: 'Alibaba',
        confidence: 0.54,
        reason: '同样受益于中国云与 AI 应用扩张，但新闻直连度较弱。',
      },
    ],
    summary: '腾讯是这条企业 AI 新闻里最直接的权益映射。',
    risk_notes: '单一来源新闻仍需与公司后续披露交叉验证。',
    sentiment: 'positive',
    context_limitations: null,
    analyzed_at: isoMinutesAgo(4),
    analysis_error: null,
  },
};

// Token 用量统计(LLMSettingsView 的用量看板)：整体汇总、按模型/按用途拆分、近 7 日
// 趋势与月度预算进度，原内联在 client.ts 的 getLlmStats() 回退分支中，迁移到此处以便
// 生产构建能把整个 mock 模块一起 tree-shake 掉。
export const mockLlmStats: LLMStats = {
  overall: { prompt_tokens: 4200, completion_tokens: 6800, total_tokens: 11000, cost_usd: 0.0176, cost_available: true },
  models: [
    {
      model_name: 'deepseek-chat',
      prompt_tokens: 3000,
      completion_tokens: 5000,
      total_tokens: 8000,
      call_count: 12,
      cost_usd: 0.011,
      cost_available: true,
      input_price_per_1k: 0.0002,
      output_price_per_1k: 0.002,
    },
    {
      model_name: 'gpt-4o',
      prompt_tokens: 1200,
      completion_tokens: 1800,
      total_tokens: 3000,
      call_count: 4,
      cost_usd: 0.0066,
      cost_available: true,
      input_price_per_1k: 0.0025,
      output_price_per_1k: 0.002,
    },
  ],
  operations: [
    { operation_type: 'chat', total_tokens: 6500 },
    { operation_type: 'analysis', total_tokens: 4500 },
  ],
  daily: [
    { date: '2026-06-06', prompt_tokens: 500, completion_tokens: 800, total_tokens: 1300 },
    { date: '2026-06-07', prompt_tokens: 600, completion_tokens: 900, total_tokens: 1500 },
    { date: '2026-06-08', prompt_tokens: 800, completion_tokens: 1200, total_tokens: 2000 },
    { date: '2026-06-09', prompt_tokens: 400, completion_tokens: 700, total_tokens: 1100 },
    { date: '2026-06-10', prompt_tokens: 900, completion_tokens: 1400, total_tokens: 2300 },
    { date: '2026-06-11', prompt_tokens: 300, completion_tokens: 600, total_tokens: 900 },
    { date: '2026-06-12', prompt_tokens: 700, completion_tokens: 1200, total_tokens: 1900 },
  ],
  budget: {
    month: '2026-06',
    month_cost_usd: 0.0176,
    monthly_budget_usd: 5,
    budget_available: true,
    over_budget: false,
    usage_ratio: 0.0035,
  },
};

export const mockWatchlistAiInsights: Record<string, { symbol: string; insight_text: string; generated_at: string }> = {
  '0700.HK': {
    symbol: '0700.HK',
    insight_text: `# AI 投研研判简报 (0700.HK)

## 1. 核心利好梳理
- **云AI代理线扩张**：公司正积极布局企业级 AI Agent 工作流，将在下个财报周期前进一步扩大云业务在 AI 商业化层面的想象空间，有望显著提振云基础设施和SaaS订阅收入。
- **估值修复资金回流**：港股本地及北向资金对大型互联网巨头重现增量兴趣，提供坚实的资金面支撑。

## 2. 核心利空与潜在风险
- **地缘与宏观环境**：AI 芯片与技术出口限制措施仍对国内云计算的长效发展构成不可忽略的底层硬件采购阻力。
- **竞争加剧**：企业服务市场上国内同行竞争依然激烈，产品落地与商业变现周期可能偏长。

## 3. 后市策略研判
- **短期情绪**：偏乐观。AI Agent 的推进能够为大模型板块及公司自身提供催化点，短期资金情绪良好。
- **中长期基本面**：向好。腾讯凭借庞大的用户基数与企业服务底座（企业微信、腾讯会议等），在 AI 落地方面转化效率极高，中长期依然具备稳固的商业溢价。`,
    generated_at: new Date().toISOString()
  }
};

// 自选股 AI 投研简报的兜底默认值：symbol 未命中 mockWatchlistAiInsights 精选样例时走这里，
// 原内联在 client.ts 的 getWatchlistAiInsight() 回退分支中，迁移到此处保持行为不变。
export const buildMockWatchlistAiInsight = (symbol: string): WatchlistAiInsight => ({
  symbol,
  insight_text: `这是关于 ${symbol} 的模拟 AI 洞察报告。该个股近期展现了一定的增长潜力。`,
  generated_at: new Date().toISOString(),
});
