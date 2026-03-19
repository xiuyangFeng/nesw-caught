import type {
  FeishuNotifyConfig,
  FeishuTestResult,
  HealthStatus,
  LLMConfigSummary,
  LLMTranslateResponse,
  MarketSnapshot,
  NewsAnalysis,
  NewsDetail,
  NewsItem,
  NewsRefreshResult,
  StockQuoteDetail,
  StreamEnvelope,
  StreamStatus,
  TopicItem,
  TopicDetail,
  WatchlistCandidate,
  WatchlistItem,
  WatchlistQuoteSummary,
  XAccount,
  XHealth,
  XPost,
  XRefreshResult,
} from '../types/api';

const now = new Date();

const isoMinutesAgo = (minutes: number) => new Date(now.getTime() - minutes * 60_000).toISOString();
const isoMinutesFromNow = (minutes: number) => new Date(now.getTime() + minutes * 60_000).toISOString();

export const mockHealth: HealthStatus = {
  status: 'ok',
  app_name: 'News Caught Backend',
  environment: 'development',
  now_utc: now.toISOString(),
  database: 'configured',
  stream_mode: 'sse',
  ai_enabled: false,
};

export const mockNews: NewsItem[] = [
  {
    id: 101,
    title: 'Tencent cloud AI product line expands to enterprise agents',
    summary: 'Enterprise-facing AI agent tooling broadens Tencent cloud narrative before the next earnings cycle.',
    source_name: 'Reuters',
    canonical_url: 'https://example.com/tencent-cloud-ai',
    market: 'hk',
    sentiment_label: 'positive',
    published_at: isoMinutesAgo(32),
    fetched_at: isoMinutesAgo(29),
  },
  {
    id: 102,
    title: 'Apple supplier guides lower on smartphone components demand',
    summary: 'Supply chain caution raises near-term pressure for US hardware names and related semiconductor sentiment.',
    source_name: 'Bloomberg',
    canonical_url: 'https://example.com/apple-supplier-demand',
    market: 'us',
    sentiment_label: 'negative',
    published_at: isoMinutesAgo(25),
    fetched_at: isoMinutesAgo(23),
  },
  {
    id: 103,
    title: 'Hong Kong brokers see renewed interest in internet platform names',
    summary: 'Broker commentary points to improved risk appetite across large-cap internet leaders.',
    source_name: 'AAStocks',
    canonical_url: 'https://example.com/hk-brokers-platform',
    market: 'hk',
    sentiment_label: 'neutral',
    published_at: isoMinutesAgo(14),
    fetched_at: isoMinutesAgo(12),
  },
  {
    id: 104,
    title: 'Nvidia ecosystem rally lifts AI infrastructure theme',
    summary: 'Data center commentary continues to cluster around AI spending durability and component tightness.',
    source_name: 'CNBC',
    canonical_url: 'https://example.com/nvidia-ecosystem-rally',
    market: 'us',
    sentiment_label: 'positive',
    published_at: isoMinutesAgo(9),
    fetched_at: isoMinutesAgo(8),
  },
];

export const mockNewsDetails: Record<number, NewsDetail> = {
  101: {
    ...mockNews[0],
    sentiment_score: 0.74,
    article: {
      content_text: 'Tencent focuses on enterprise AI agents and cloud workflow integration in the latest expansion update.',
      extract_status: 'success',
      extract_error: null,
      extracted_at: isoMinutesAgo(28),
    },
    mentions: [
      { symbol: '0700.HK', market: 'hk', mention_type: 'primary', confidence: 0.96 },
      { symbol: '9988.HK', market: 'hk', mention_type: 'secondary', confidence: 0.66 },
    ],
    topic: {
      id: 501,
      topic_title: 'China internet AI monetization',
      importance_score: 0.83,
      last_seen_at: isoMinutesAgo(12),
    },
  },
  102: {
    ...mockNews[1],
    sentiment_score: -0.61,
    article: {
      content_text: null,
      extract_status: 'failed',
      extract_error: 'source blocked extractor',
      extracted_at: isoMinutesAgo(21),
    },
    mentions: [{ symbol: 'AAPL', market: 'us', mention_type: 'primary', confidence: 0.91 }],
    topic: {
      id: 502,
      topic_title: 'US smartphone demand softness',
      importance_score: 0.78,
      last_seen_at: isoMinutesAgo(20),
    },
  },
  103: {
    ...mockNews[2],
    sentiment_score: 0.12,
    article: {
      content_text: 'Local brokers highlighted valuation repair and incremental northbound capital interest.',
      extract_status: 'success',
      extract_error: null,
      extracted_at: isoMinutesAgo(10),
    },
    mentions: [{ symbol: '0700.HK', market: 'hk', mention_type: 'secondary', confidence: 0.72 }],
    topic: {
      id: 503,
      topic_title: 'Hong Kong internet sentiment stabilization',
      importance_score: 0.63,
      last_seen_at: isoMinutesAgo(11),
    },
  },
  104: {
    ...mockNews[3],
    sentiment_score: 0.88,
    article: {
      content_text: 'AI infrastructure names remain tightly linked to supply chain guidance and hyperscaler capex commentary.',
      extract_status: 'success',
      extract_error: null,
      extracted_at: isoMinutesAgo(7),
    },
    mentions: [
      { symbol: 'NVDA', market: 'us', mention_type: 'primary', confidence: 0.98 },
      { symbol: 'TSM', market: 'us', mention_type: 'secondary', confidence: 0.75 },
    ],
    topic: {
      id: 504,
      topic_title: 'AI infrastructure capex theme',
      importance_score: 0.94,
      last_seen_at: isoMinutesAgo(8),
    },
  },
};

export const mockLlmConfig: LLMConfigSummary = {
  configured: true,
  provider_name: 'openai_compatible',
  display_name: 'OpenAI Compatible',
  model_name: 'deepseek-chat',
  base_url: 'https://example-llm.test/v1',
  api_key_set: true,
  updated_at: isoMinutesAgo(5),
};

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

export const mockMarketSnapshots: MarketSnapshot[] = [
  {
    symbol: '0700.HK',
    market: 'hk',
    display_name: 'Tencent',
    provider_symbol: '0700.HK',
    price: 332.4,
    change_amount: 10.7,
    change_percent: 3.33,
    open_price: 325.0,
    previous_close: 321.7,
    day_high: 334.8,
    day_low: 323.2,
    volume: 18233000,
    status: 'ok',
    source: 'yahoo_finance',
    message: null,
    is_abnormal: true,
    abnormal_reason: 'volume_spike',
    fetched_at: isoMinutesAgo(2),
  },
  {
    symbol: '9988.HK',
    market: 'hk',
    display_name: 'Alibaba',
    provider_symbol: '9988.HK',
    price: 86.2,
    change_amount: 1.1,
    change_percent: 1.29,
    open_price: 85.6,
    previous_close: 85.1,
    day_high: 86.7,
    day_low: 85.0,
    volume: 9320000,
    status: 'ok',
    source: 'yahoo_finance',
    message: null,
    is_abnormal: false,
    abnormal_reason: null,
    fetched_at: isoMinutesAgo(3),
  },
  {
    symbol: 'AAPL',
    market: 'us',
    display_name: 'Apple',
    provider_symbol: 'AAPL',
    price: 215.32,
    change_amount: -2.84,
    change_percent: -1.3,
    open_price: 217.1,
    previous_close: 218.16,
    day_high: 219.4,
    day_low: 214.8,
    volume: 18230000,
    status: 'ok',
    source: 'yahoo_finance',
    message: null,
    is_abnormal: false,
    abnormal_reason: null,
    fetched_at: isoMinutesAgo(4),
  },
  {
    symbol: 'NVDA',
    market: 'us',
    display_name: 'NVIDIA',
    provider_symbol: 'NVDA',
    price: 932.18,
    change_amount: 38.11,
    change_percent: 4.26,
    open_price: 910.0,
    previous_close: 894.07,
    day_high: 935.4,
    day_low: 905.6,
    volume: 42456000,
    status: 'ok',
    source: 'yahoo_finance',
    message: null,
    is_abnormal: true,
    abnormal_reason: 'price_breakout',
    fetched_at: isoMinutesAgo(1),
  },
];

export const mockWatchlistQuotes: WatchlistQuoteSummary[] = [
  mockMarketSnapshots[0],
  {
    symbol: 'HK253',
    market: 'hk',
    display_name: '智谱',
    provider_symbol: '0253.HK',
    price: 18.25,
    change_amount: 0.5,
    change_percent: 2.82,
    open_price: 17.9,
    previous_close: 17.75,
    day_high: 18.4,
    day_low: 17.6,
    volume: 1200000,
    status: 'ok',
    source: 'yahoo_finance',
    message: null,
    is_abnormal: false,
    abnormal_reason: null,
    fetched_at: isoMinutesAgo(2),
  },
  mockMarketSnapshots[2],
];

export const mockStockQuoteDetails: Record<string, StockQuoteDetail> = Object.fromEntries(
  mockWatchlistQuotes.map((item) => [item.symbol, item]),
);

export const mockWatchlist: WatchlistItem[] = [
  {
    id: 1,
    symbol: '0700.HK',
    market: 'hk',
    display_name: 'Tencent',
    is_active: true,
    alert_threshold: 3,
    alert_mode: 'fixed',
  },
  {
    id: 2,
    symbol: '9988.HK',
    market: 'hk',
    display_name: 'Alibaba',
    is_active: true,
    alert_threshold: 3,
    alert_mode: 'fixed',
  },
  {
    id: 3,
    symbol: 'AAPL',
    market: 'us',
    display_name: 'Apple',
    is_active: true,
    alert_threshold: 2,
    alert_mode: 'fixed',
  },
  {
    id: 4,
    symbol: 'NVDA',
    market: 'us',
    display_name: 'NVIDIA',
    is_active: true,
    alert_threshold: 4,
    alert_mode: 'fixed',
  },
];

export const mockWatchlistCandidates: WatchlistCandidate[] = [
  {
    symbol: '0700.HK',
    market: 'hk',
    display_name: 'Tencent',
    aliases: ['腾讯', '腾讯控股', '700', '0700', 'tencent holdings'],
  },
  {
    symbol: '9988.HK',
    market: 'hk',
    display_name: 'Alibaba',
    aliases: ['阿里', '阿里巴巴', '9988', 'baba', 'alibaba group'],
  },
  {
    symbol: 'AAPL',
    market: 'us',
    display_name: 'Apple',
    aliases: ['苹果', 'apple inc'],
  },
  {
    symbol: 'NVDA',
    market: 'us',
    display_name: 'NVIDIA',
    aliases: ['英伟达', 'nvidia corp'],
  },
  {
    symbol: 'TME',
    market: 'us',
    display_name: 'Tencent Music',
    aliases: ['腾讯音乐', 'tencent music entertainment'],
  },
];

export const mockTopics: TopicItem[] = [
  {
    id: 501,
    topic_title: 'China internet AI monetization',
    topic_summary: 'Platform companies are reframing AI spending around cloud and enterprise monetization.',
    keywords: ['AI', 'cloud', 'enterprise'],
    market: 'hk',
    sentiment_label: 'positive',
    importance_score: 0.83,
    news_count: 4,
    last_seen_at: isoMinutesAgo(12),
    related_symbols: ['0700.HK', '9988.HK'],
  },
  {
    id: 504,
    topic_title: 'AI infrastructure capex theme',
    topic_summary: 'Capex commentary continues to reinforce the AI infrastructure leaders.',
    keywords: ['AI', 'semis', 'capex'],
    market: 'us',
    sentiment_label: 'positive',
    importance_score: 0.94,
    news_count: 7,
    last_seen_at: isoMinutesAgo(8),
    related_symbols: ['NVDA', 'TSM'],
  },
  {
    id: 502,
    topic_title: 'US smartphone demand softness',
    topic_summary: 'Supplier guidance points to a softer demand environment for near-term hardware shipments.',
    keywords: ['smartphone', 'demand', 'supply-chain'],
    market: 'us',
    sentiment_label: 'negative',
    importance_score: 0.78,
    news_count: 3,
    last_seen_at: isoMinutesAgo(20),
    related_symbols: ['AAPL'],
  },
];

export const mockTopicDetails: Record<number, TopicDetail> = {
  501: {
    ...mockTopics[0],
    sources: [mockNews[0], mockNews[2]],
  },
  504: {
    ...mockTopics[1],
    sources: [mockNews[3]],
  },
  502: {
    ...mockTopics[2],
    sources: [mockNews[1]],
  },
};

export const mockRelatedNews: Record<string, NewsItem[]> = {
  '0700.HK': [mockNews[0], mockNews[2]],
  AAPL: [mockNews[1]],
  NVDA: [mockNews[3]],
};

export const mockStreamStatus: StreamStatus = {
  mode: 'sse',
  status: 'planned',
  last_event_at: isoMinutesAgo(1),
  retry_interval_ms: 3000,
};

export const mockXHealth: XHealth = {
  enabled: true,
  configured: true,
  healthy: true,
  status: 'configured',
  provider_name: 'twitterapi.io',
  min_interval_seconds: 6,
  refresh_cooldown_hours: 3,
  last_success_at: isoMinutesAgo(6),
  last_failure_at: null,
  consecutive_failures: 0,
  total_fetches: 2,
  total_failures: 0,
  avg_latency_ms: 2410,
  last_error: null,
};

export const mockXAccounts: XAccount[] = [
  {
    id: 1,
    handle: 'MiniMax_AI',
    display_name: 'MiniMax AI',
    market_focus: 'us',
    is_active: true,
    priority: 100,
    notes: 'Official MiniMax AI account updates',
  },
];

export const mockXPosts: XPost[] = [
  {
    id: 1,
    account_handle: 'DeItaone',
    account_display_name: 'Delta One',
    content_text: 'NVIDIA suppliers remain in focus as AI infrastructure demand signals stay firm into the next quarter.',
    canonical_url: 'https://x.com/DeItaone/status/190001',
    market: 'us',
    sentiment_label: 'positive',
    relevance_score: 0.92,
    posted_at: isoMinutesAgo(13),
    captured_at: isoMinutesAgo(5),
    symbols: ['NVDA'],
  },
  {
    id: 2,
    account_handle: 'SawyerMerritt',
    account_display_name: 'Sawyer Merritt',
    content_text: 'Tesla supply chain comments are weighing on near-term EV sentiment after softer delivery expectations.',
    canonical_url: 'https://x.com/SawyerMerritt/status/190002',
    market: 'us',
    sentiment_label: 'negative',
    relevance_score: 0.84,
    posted_at: isoMinutesAgo(18),
    captured_at: isoMinutesAgo(6),
    symbols: ['TSLA'],
  },
  {
    id: 3,
    account_handle: 'SawyerMerritt',
    account_display_name: 'Sawyer Merritt',
    content_text: 'NVDA demand remains strong as AI servers and networking orders stay elevated.',
    canonical_url: 'https://x.com/SawyerMerritt/status/190003',
    market: 'us',
    sentiment_label: 'unknown',
    relevance_score: null,
    posted_at: isoMinutesAgo(9),
    captured_at: isoMinutesAgo(3),
    symbols: ['NVDA'],
  },
];

export const mockXRefreshResult: XRefreshResult = {
  started_at: isoMinutesAgo(1),
  finished_at: isoMinutesAgo(1),
  fetched_count: 2,
  inserted_count: 1,
  error: null,
  latency_ms: 2634,
  skipped: false,
  skip_reason: null,
  next_refresh_at: isoMinutesFromNow(179),
};

export const mockNewsRefreshResult: NewsRefreshResult = {
  started_at: isoMinutesAgo(1),
  finished_at: isoMinutesAgo(1),
  fetched_count: 4,
  inserted_count: 0,
  results: [],
};

export const mockStreamEvents: StreamEnvelope[] = [
  {
    type: 'stream.keepalive',
    occurred_at: isoMinutesAgo(1),
    payload: { status: 'ok' },
  },
];

export const mockFeishuConfig: FeishuNotifyConfig = {
  configured: false,
  app_id: null,
  app_secret_set: false,
  target_type: null,
  target_id: null,
  news_enabled: true,
  news_keywords: null,
  news_batch_interval_minutes: 60,
  alert_enabled: true,
  analysis_enabled: true,
  is_active: true,
  updated_at: null,
};

export const mockFeishuTestResult: FeishuTestResult = {
  success: true,
  message: '测试消息发送成功（mock）',
};
