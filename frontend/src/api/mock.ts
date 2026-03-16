import type {
  HealthStatus,
  MarketSnapshot,
  NewsDetail,
  NewsItem,
  StreamEnvelope,
  StreamStatus,
  TopicItem,
  TopicDetail,
  WatchlistItem,
} from '../types/api';

const now = new Date();

const isoMinutesAgo = (minutes: number) => new Date(now.getTime() - minutes * 60_000).toISOString();

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

export const mockMarketSnapshots: MarketSnapshot[] = [
  {
    symbol: '0700.HK',
    market: 'hk',
    display_name: 'Tencent',
    price: 332.4,
    change_amount: 10.7,
    change_percent: 3.33,
    volume: 18233000,
    is_abnormal: true,
    abnormal_reason: 'volume_spike',
    fetched_at: isoMinutesAgo(2),
  },
  {
    symbol: '9988.HK',
    market: 'hk',
    display_name: 'Alibaba',
    price: 86.2,
    change_amount: 1.1,
    change_percent: 1.29,
    volume: 9320000,
    is_abnormal: false,
    abnormal_reason: null,
    fetched_at: isoMinutesAgo(3),
  },
  {
    symbol: 'AAPL',
    market: 'us',
    display_name: 'Apple',
    price: 215.32,
    change_amount: -2.84,
    change_percent: -1.3,
    volume: 18230000,
    is_abnormal: false,
    abnormal_reason: null,
    fetched_at: isoMinutesAgo(4),
  },
  {
    symbol: 'NVDA',
    market: 'us',
    display_name: 'NVIDIA',
    price: 932.18,
    change_amount: 38.11,
    change_percent: 4.26,
    volume: 42456000,
    is_abnormal: true,
    abnormal_reason: 'price_breakout',
    fetched_at: isoMinutesAgo(1),
  },
];

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

export const mockStreamEvents: StreamEnvelope[] = [
  {
    type: 'stream.keepalive',
    occurred_at: isoMinutesAgo(1),
    payload: { status: 'ok' },
  },
];
