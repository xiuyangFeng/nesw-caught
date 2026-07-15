// LLM 域 mock 数据：大模型接入配置、翻译、新闻个股映射分析(NewsAnalysis)，
// 以及自选股 AI 投研简报文本(WatchlistAiInsight)。

import type { LLMConfigSummary, LLMTranslateResponse, NewsAnalysis } from '../../types/api';
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
