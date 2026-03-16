export type Market = 'hk' | 'us' | 'cn';
export type SentimentLabel = 'positive' | 'negative' | 'neutral' | 'mixed' | 'unknown';
export type ExtractStatus = 'pending' | 'success' | 'failed' | 'not_requested';

export interface HealthStatus {
  status: string;
  app_name: string;
  environment: string;
  now_utc: string;
  database: string;
  stream_mode: string;
  ai_enabled: boolean;
  x_bridge_enabled?: boolean;
  x_bridge_healthy?: boolean;
}

export interface NewsItem {
  id: number;
  title: string;
  summary: string | null;
  source_name: string;
  canonical_url: string | null;
  market: Market;
  sentiment_label: SentimentLabel;
  published_at: string;
  fetched_at: string;
}

export interface NewsMention {
  symbol: string;
  market: Market;
  mention_type: string;
  confidence: number;
}

export interface NewsTopicRef {
  id: number;
  topic_title: string;
  importance_score: number;
  last_seen_at: string;
}

export interface NewsArticle {
  content_text: string | null;
  extract_status: ExtractStatus;
  extract_error: string | null;
  extracted_at: string | null;
}

export interface NewsDetail extends NewsItem {
  sentiment_score: number | null;
  article: NewsArticle | null;
  mentions: NewsMention[];
  topic: NewsTopicRef | null;
}

export interface MarketSnapshot {
  symbol: string;
  market: Market;
  display_name: string | null;
  provider_symbol: string | null;
  price: number | null;
  change_amount: number | null;
  change_percent: number | null;
  open_price: number | null;
  previous_close: number | null;
  day_high: number | null;
  day_low: number | null;
  volume: number | null;
  status: 'ok' | 'delayed' | 'unavailable' | 'symbol_not_supported' | 'fetch_failed';
  source: string | null;
  message: string | null;
  is_abnormal: boolean;
  abnormal_reason: string | null;
  fetched_at: string;
}

export interface WatchlistQuoteSummary extends MarketSnapshot {}

export interface StockQuoteDetail extends WatchlistQuoteSummary {}

export interface WatchlistItem {
  id: number;
  symbol: string;
  market: Market;
  display_name: string;
  is_active: boolean;
  alert_threshold: number | null;
  alert_mode: string;
}

export interface WatchlistItemCreate {
  symbol: string;
  market: Market;
  display_name: string;
  alert_threshold: number | null;
  alert_mode: string;
}

export interface TopicItem {
  id: number;
  topic_title: string;
  topic_summary: string | null;
  keywords: string[];
  market: Market;
  sentiment_label: SentimentLabel;
  importance_score: number;
  news_count: number;
  last_seen_at: string;
  related_symbols: string[];
}

export interface TopicDetail extends TopicItem {
  sources: NewsItem[];
}

export interface StreamStatus {
  mode: string;
  status: string;
  last_event_at: string | null;
  retry_interval_ms: number | null;
}

export interface StreamEventMap {
  'news.created': NewsItem;
  'topic.updated': Pick<TopicItem, 'id' | 'topic_title' | 'market' | 'importance_score' | 'news_count' | 'last_seen_at'>;
  'watchlist.movement': MarketSnapshot;
  'stream.keepalive': { status: 'ok' };
}

export type StreamEventType = keyof StreamEventMap;

export interface StreamEnvelope<T extends StreamEventType = StreamEventType> {
  type: T;
  occurred_at: string;
  payload: StreamEventMap[T];
}

export interface NewsQuery {
  market?: Market | '';
  q?: string;
  source_name?: string;
  sentiment_label?: SentimentLabel | '';
  limit?: number;
}

export interface XAccount {
  id: number;
  handle: string;
  display_name: string;
  market_focus: string | null;
  is_active: boolean;
  priority: number;
  notes: string | null;
}

export interface XPost {
  id: number;
  account_handle: string;
  account_display_name: string;
  content_text: string;
  canonical_url: string | null;
  market: Market;
  sentiment_label: SentimentLabel;
  relevance_score: number | null;
  posted_at: string | null;
  captured_at: string;
  symbols: string[];
}

export interface XRefreshResult {
  started_at: string;
  finished_at: string;
  fetched_count: number;
  inserted_count: number;
  error: string | null;
  latency_ms: number;
}

export interface XHealth {
  enabled: boolean;
  bridge_configured: boolean;
  bridge_healthy: boolean;
  bridge_status: string;
  provider_name: string;
  last_success_at: string | null;
  last_failure_at: string | null;
  consecutive_failures: number;
  total_fetches: number;
  total_failures: number;
  avg_latency_ms: number | null;
  last_error: string | null;
}

export interface XPostQuery {
  account_handle?: string;
  market?: Market | '';
  q?: string;
  symbol?: string;
  limit?: number;
}
