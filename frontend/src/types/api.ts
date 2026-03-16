export type Market = 'hk' | 'us';
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
  price: number;
  change_amount: number | null;
  change_percent: number;
  volume: number | null;
  is_abnormal: boolean;
  abnormal_reason: string | null;
  fetched_at: string;
}

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
