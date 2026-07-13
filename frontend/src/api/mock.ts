import type {
  FeishuNotifyConfig,
  FeishuTestResult,
  HealthStatus,
  LLMConfigSummary,
  LLMTranslateResponse,
  MarketSnapshot,
  NewsAnalysis,
  NewsDetail,
  NewsEventDetail,
  NewsFeedLayout,
  NewsEventMarker,
  NewsItem,
  NewsRuntimeStatus,
  NewsRefreshResult,
  SparklineSeries,
  StockKlineResponse,
  StockQuoteDetail,
  StreamEnvelope,
  StreamStatus,
  TopicItem,
  TopicDetail,
  WatchlistCandidate,
  WatchlistItem,
  WatchlistQuoteSummary,
  WatchlistResearchBrief,
  XAccount,
  XHealth,
  XPost,
  XRadarResponse,
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
  x_monitor_enabled: false,
  x_monitor_healthy: false,
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
    has_hot_alert: false,
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
    has_hot_alert: false,
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
    has_hot_alert: false,
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
    has_hot_alert: false,
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
    has_hot_alert: false,
    fetched_at: isoMinutesAgo(2),
  },
  {
    symbol: '600519.SH',
    market: 'cn',
    display_name: '贵州茅台',
    provider_symbol: '600519.SS',
    price: 1688.8,
    change_amount: 12.5,
    change_percent: 0.75,
    open_price: 1670.0,
    previous_close: 1676.3,
    day_high: 1699.0,
    day_low: 1668.0,
    volume: 928000,
    status: 'ok',
    source: 'yahoo_finance',
    message: null,
    has_hot_alert: false,
    fetched_at: isoMinutesAgo(2),
  },
  mockMarketSnapshots[2],
];

// QuoteDetailView 比 QuoteSummaryView 多 is_abnormal/abnormal_reason 字段,这里补默认值
export const mockStockQuoteDetails: Record<string, StockQuoteDetail> = Object.fromEntries(
  mockWatchlistQuotes.map((item) => [item.symbol, { is_abnormal: false, abnormal_reason: null, ...item }]),
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
  {
    id: 5,
    symbol: '600519.SH',
    market: 'cn',
    display_name: '贵州茅台',
    is_active: true,
    alert_threshold: 3,
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
  {
    symbol: '600519.SH',
    market: 'cn',
    display_name: '贵州茅台',
    aliases: ['茅台', '贵州茅台', '600519', 'sh600519', 'kweichow moutai'],
  },
  {
    symbol: '300750.SZ',
    market: 'cn',
    display_name: '宁德时代',
    aliases: ['宁德时代', '300750', 'sz300750', 'catl'],
  },
  {
    symbol: '000001.SZ',
    market: 'cn',
    display_name: '平安银行',
    aliases: ['平安银行', '000001', 'sz000001', 'ping an bank'],
  },
  {
    symbol: '600036.SH',
    market: 'cn',
    display_name: '招商银行',
    aliases: ['招商银行', '600036', 'sh600036', 'cmb'],
  },
  {
    symbol: '601318.SH',
    market: 'cn',
    display_name: '中国平安',
    aliases: ['中国平安', '601318', 'sh601318', 'ping an insurance'],
  },
  {
    symbol: '002594.SZ',
    market: 'cn',
    display_name: '比亚迪',
    aliases: ['比亚迪', '002594', 'sz002594', 'byd'],
  },
  {
    symbol: '688041.SH',
    market: 'cn',
    display_name: '海光信息',
    aliases: ['海光信息', '688041', 'sh688041', 'haiguang'],
  },
  {
    symbol: '688981.SH',
    market: 'cn',
    display_name: '中芯国际',
    aliases: ['中芯国际', '688981', 'sh688981', 'smic'],
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

export const mockNewsFeedLayout: NewsFeedLayout = {
  events: [
    {
      event_key: 'topic-504',
      event_title: 'AI infrastructure capex theme',
      event_summary: 'AI 基础设施支出与供应链紧张度继续强化，首页优先显示为事件主卡。',
      event_type: 'product',
      market: 'us',
      sentiment_label: 'positive',
      importance_score: 0.94,
      last_seen_at: mockTopics[1].last_seen_at,
      primary_symbol: 'NVDA',
      related_symbols: ['NVDA', 'TSM'],
      source_count: 2,
      news_count: 2,
      news_items: [mockNews[3], mockNews[1]],
    },
    {
      event_key: 'topic-501',
      event_title: 'China internet AI monetization',
      event_summary: '中国互联网平台围绕企业 AI 商业化展开新一轮叙事。',
      event_type: 'product',
      market: 'hk',
      sentiment_label: 'positive',
      importance_score: 0.83,
      last_seen_at: mockTopics[0].last_seen_at,
      primary_symbol: '0700.HK',
      related_symbols: ['0700.HK', '9988.HK'],
      source_count: 2,
      news_count: 2,
      news_items: [mockNews[0], mockNews[2]],
    },
  ],
  topics: mockTopics.slice(0, 3),
  stream: mockNews,
};

export const mockNewsEventDetails: Record<string, NewsEventDetail> = {
  'topic-504': {
    ...mockNewsFeedLayout.events[0],
    news_items: [mockNews[3], mockNews[1]],
  },
  'topic-501': {
    ...mockNewsFeedLayout.events[1],
    news_items: [mockNews[0], mockNews[2]],
  },
};

export const mockRelatedNews: Record<string, NewsItem[]> = {
  '0700.HK': [mockNews[0], mockNews[2]],
  AAPL: [mockNews[1]],
  NVDA: [mockNews[3]],
};

export const mockWatchlistResearchBriefs: Record<string, WatchlistResearchBrief> = {
  '0700.HK': {
    symbol: '0700.HK',
    market: 'hk',
    generated_at: isoMinutesAgo(5),
    window_days: 14,
    top_action_level: 'act_now',
    has_unexplained_price_move: false,
    drivers: [
      {
        category: 'company_action',
        action_level: 'act_now',
        reason: '公司动作或订单变化可能改变未来催化节奏。优先级高，建议立即核对原文。',
        news_item: mockNews[0],
      },
    ],
  },
  AAPL: {
    symbol: 'AAPL',
    market: 'us',
    generated_at: isoMinutesAgo(5),
    window_days: 14,
    top_action_level: 'watch_today',
    has_unexplained_price_move: false,
    drivers: [
      {
        category: 'supply_chain',
        action_level: 'watch_today',
        reason: '产业链供需或价格变化值得继续跟踪传导路径。建议今天内完成确认。',
        news_item: mockNews[1],
      },
    ],
  },
  NVDA: {
    symbol: 'NVDA',
    market: 'us',
    generated_at: isoMinutesAgo(5),
    window_days: 14,
    top_action_level: 'watch_today',
    has_unexplained_price_move: false,
    drivers: [
      {
        category: 'supply_chain',
        action_level: 'watch_today',
        reason: '产业链供需或价格变化值得继续跟踪传导路径。建议今天内完成确认。',
        news_item: mockNews[3],
      },
    ],
  },
};

const buildMockNewsEvents = (symbol: string): NewsEventMarker[] =>
  (mockRelatedNews[symbol] ?? []).slice(0, 2).map((item) => ({
    time: (item.published_at ?? item.fetched_at).slice(0, 10),
    items: [{ id: item.id, title: item.title, sentiment: item.sentiment_label ?? 'unknown', summary: item.summary ?? '' }],
  }));

export const mockStockKlines: Record<string, StockKlineResponse> = Object.fromEntries(
  Object.keys(mockStockQuoteDetails).map((symbol) => [
    symbol,
    {
      symbol,
      interval: '1d',
      range: '6mo',
      stale: false,
      candles: Array.from({ length: 12 }, (_, index) => ({
        time: new Date(now.getTime() - (11 - index) * 86_400_000).toISOString().slice(0, 10),
        open: 500 + index,
        high: 504 + index,
        low: 497 + index,
        close: 501 + index,
        volume: 1000 + index * 100,
      })),
      indicators: {
        ma5: [],
        ma10: [],
        ma20: [],
        ma60: [],
        macd: [],
        kdj: [],
        bollinger: [],
      },
      news_events: buildMockNewsEvents(symbol),
    },
  ]),
);

export const mockWatchlistSparklines: Record<string, SparklineSeries> = Object.fromEntries(
  Object.keys(mockStockQuoteDetails).map((symbol) => [
    symbol,
    {
      prices: Array.from({ length: 12 }, (_, index) => 100 + index * 2),
    },
  ]),
);

export const mockStreamStatus: StreamStatus = {
  mode: 'sse',
  status: 'ok',
  backend: 'memory',
  redis_enabled: false,
  last_published_at: isoMinutesAgo(1),
  last_event_name: 'news.created',
  last_error: null,
  market_worker: null,
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
    tier: 'core',
    source: 'manual',
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

export const mockXRadar: XRadarResponse = {
  priority_signals: [
    {
      id: 1,
      signal_type: 'macro_event',
      title: 'Tariff pressure is building around AI semis',
      summary: 'Tracked accounts are flagging tariff and export-control risk around AI chip supply chains before the news cycle fully catches up.',
      market: 'us',
      topic_tag: 'macro',
      macro_tag: 'tariff',
      primary_symbol: 'NVDA',
      priority_score: 95,
      confidence_score: 0.88,
      source_count: 2,
      first_seen_at: isoMinutesAgo(24),
      last_seen_at: isoMinutesAgo(8),
    },
    {
      id: 2,
      signal_type: 'multi_account_resonance',
      title: 'Fed path discussion is starting to converge',
      summary: 'Multiple tracked accounts are reacting to rate-cut odds and CPI language in the same window.',
      market: 'us',
      topic_tag: 'macro',
      macro_tag: 'rate',
      primary_symbol: 'SPY',
      priority_score: 89,
      confidence_score: 0.83,
      source_count: 3,
      first_seen_at: isoMinutesAgo(36),
      last_seen_at: isoMinutesAgo(12),
    },
  ],
  macro_clusters: [
    {
      macro_tag: 'tariff',
      title: 'Tariff Watch',
      signal_count: 1,
      source_count: 2,
      top_signal_ids: [1],
    },
    {
      macro_tag: 'rate',
      title: 'Rate Watch',
      signal_count: 1,
      source_count: 3,
      top_signal_ids: [2],
    },
  ],
  evidence_stream: mockXPosts,
};

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

export const mockNewsRuntimeStatus: NewsRuntimeStatus = {
  feed_status: 'degraded',
  last_refresh_finished_at: isoMinutesAgo(2),
  last_news_created_at: isoMinutesAgo(6),
  last_incremental_event_at: isoMinutesAgo(5),
  degraded_market_count: 1,
  markets: [
    {
      market: 'us',
      status: 'live',
      mode: 'primary',
      last_primary_success_at: isoMinutesAgo(3),
      last_news_created_at: isoMinutesAgo(6),
      degraded_reason: null,
    },
    {
      market: 'hk',
      status: 'degraded',
      mode: 'secondary',
      last_primary_success_at: isoMinutesAgo(45),
      last_news_created_at: isoMinutesAgo(8),
      degraded_reason: 'primary sources failing; fallback supply active',
    },
  ],
  sources: [
    {
      source_name: 'Reuters',
      market: 'us',
      tier: 'primary',
      status: 'ok',
      last_attempt_at: isoMinutesAgo(3),
      last_success_at: isoMinutesAgo(3),
      consecutive_failures: 0,
      avg_fetch_latency_ms: 280,
      latest_news_published_at: isoMinutesAgo(10),
      latest_news_fetched_at: isoMinutesAgo(6),
      last_error: null,
    },
    {
      source_name: 'AAStocks',
      market: 'hk',
      tier: 'secondary',
      status: 'degraded',
      last_attempt_at: isoMinutesAgo(4),
      last_success_at: isoMinutesAgo(8),
      consecutive_failures: 2,
      avg_fetch_latency_ms: 410,
      latest_news_published_at: isoMinutesAgo(12),
      latest_news_fetched_at: isoMinutesAgo(8),
      last_error: 'upstream timeout',
    },
  ],
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
  governance: {
    quiet_hours_start: null,
    quiet_hours_end: null,
    quiet_hours_tz: 'Asia/Shanghai',
    dedupe_window_minutes: 0,
    digest_window_minutes: 0,
    digest_threshold: 3,
    critical_change_percent: 8,
  },
};

export const mockFeishuTestResult: FeishuTestResult = {
  success: true,
  message: '测试消息发送成功（mock）',
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
