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
  x_monitor_enabled?: boolean;
  x_monitor_healthy?: boolean;
}

export interface NewsItem {
  id: number;
  title: string;
  summary: string | null;
  source_name: string;
  canonical_url: string | null;
  market: Market;
  sentiment_label: SentimentLabel;
  published_at: string | null;
  fetched_at: string;
  editorial_score?: number | null;
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

export interface NewsFeedEventCard {
  event_key: string;
  event_title: string;
  event_summary: string | null;
  event_type: string;
  market: Market;
  sentiment_label: SentimentLabel;
  importance_score: number;
  last_seen_at: string | null;
  primary_symbol: string | null;
  related_symbols: string[];
  source_count: number;
  news_count: number;
  news_items: NewsItem[];
}

export interface NewsFeedTopic {
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

export interface NewsFeedLayout {
  events: NewsFeedEventCard[];
  topics: NewsFeedTopic[];
  stream: NewsItem[];
}

export interface NewsRuntimeSource {
  source_name: string;
  market: Market;
  tier: string;
  status: 'ok' | 'delayed' | 'degraded' | 'offline';
  last_attempt_at: string | null;
  last_success_at: string | null;
  consecutive_failures: number;
  avg_fetch_latency_ms: number | null;
  latest_news_published_at: string | null;
  latest_news_fetched_at: string | null;
  last_error: string | null;
}

export interface NewsRuntimeMarket {
  market: Market;
  status: 'live' | 'delayed' | 'degraded' | 'offline';
  mode: 'primary' | 'secondary' | 'fallback' | 'none';
  last_primary_success_at: string | null;
  last_news_created_at: string | null;
  degraded_reason: string | null;
}

export interface NewsRuntimeStatus {
  feed_status: 'live' | 'delayed' | 'degraded';
  last_refresh_finished_at: string | null;
  last_news_created_at: string | null;
  last_incremental_event_at: string | null;
  degraded_market_count: number;
  markets: NewsRuntimeMarket[];
  sources: NewsRuntimeSource[];
}

export interface NewsUpdateEvent extends NewsItem {
  updated_fields: string[];
}

export interface LLMConfigSummary {
  configured: boolean;
  provider_name: string | null;
  display_name: string | null;
  model_name: string | null;
  base_url: string | null;
  api_key_set: boolean;
  updated_at: string | null;
}

export interface LLMConfigUpdateRequest {
  provider_name: string;
  model_name: string;
  display_name?: string | null;
  base_url?: string | null;
  api_key?: string;
}

export interface LLMTranslateRequest {
  text: string;
}

export interface LLMTranslateResponse {
  provider_name: string;
  model_name: string;
  translated_text: string;
}

export interface LLMConnectionTestResponse {
  provider_name: string;
  model_name: string;
  message: string;
}

export interface NewsAnalysisCandidate {
  symbol: string;
  market: Market;
  company_name: string | null;
  confidence: number | null;
  reason: string;
}

export interface NewsAnalysis {
  news_id: number;
  provider_name: string;
  model_name: string;
  analysis_status: string;
  top_pick: NewsAnalysisCandidate | null;
  candidates: NewsAnalysisCandidate[];
  summary: string | null;
  risk_notes: string | null;
  sentiment: SentimentLabel | string | null;
  context_limitations: string | null;
  analyzed_at: string;
  analysis_error: string | null;
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

export interface WatchlistCandidate {
  symbol: string;
  market: Market;
  display_name: string;
  aliases: string[];
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
  backend: string;
  redis_enabled: boolean;
  last_published_at: string | null;
  last_event_name: string | null;
  last_error: string | null;
  market_worker: MarketWorkerStatus | null;
}

export interface MarketWorkerStatus {
  name: string;
  status: string;
  last_heartbeat_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_error: string | null;
  cycle_count: number;
  success_count: number;
  failure_count: number;
  last_quotes_count: number;
}

export interface MarketRefreshResult {
  quotes_count: number;
  symbols: string[];
  triggered_at: string;
}

export type WatchlistDashboardPeriod = '1D' | '1W' | '1M' | '1Y';

export interface KlineCandle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface KlineValuePoint {
  time: string;
  value: number;
}

export interface KlineMacdPoint {
  time: string;
  dif: number;
  dea: number;
  histogram: number;
}

export interface KlineKdjPoint {
  time: string;
  k: number;
  d: number;
  j: number;
}

export interface KlineBollingerPoint {
  time: string;
  upper: number;
  middle: number;
  lower: number;
}

export interface NewsEventMarkerItem {
  id: number;
  title: string;
  sentiment: SentimentLabel | string;
  summary: string;
}

export interface NewsEventMarker {
  time: string;
  items: NewsEventMarkerItem[];
}

export interface KlineIndicators {
  ma5: KlineValuePoint[];
  ma10: KlineValuePoint[];
  ma20: KlineValuePoint[];
  ma60: KlineValuePoint[];
  macd: KlineMacdPoint[];
  kdj: KlineKdjPoint[];
  bollinger: KlineBollingerPoint[];
}

export interface StockKlineResponse {
  symbol: string;
  interval: string;
  range: string;
  stale: boolean;
  candles: KlineCandle[];
  indicators: KlineIndicators;
  news_events: NewsEventMarker[];
}

export type KlineDrawingTool =
  | 'select'
  | 'trend_line'
  | 'horizontal_line'
  | 'price_range'
  | 'fibonacci_retracement'
  | 'price_note';

export interface KlineDrawingAnchor {
  time: string;
  price: number;
}

export interface KlineDrawingStyle {
  color: string;
  lineWidth: number;
  lineStyle: 'solid' | 'dashed';
  fillOpacity: number;
}

export interface KlineDrawingPayload {
  text?: string;
}

export interface KlineDrawing {
  id: string;
  symbol: string;
  toolType: Exclude<KlineDrawingTool, 'select'>;
  createdAt: string;
  updatedAt: string;
  locked: boolean;
  visible: boolean;
  style: KlineDrawingStyle;
  anchors: KlineDrawingAnchor[];
  payload: KlineDrawingPayload;
}

export interface VersionedPersistedValue<T> {
  version: number;
  savedAt: string;
  payload: T;
}

export type OverlayIndicatorKind = 'MA' | 'EMA' | 'BOLL';
export type KlineSubIndicator = 'VOL' | 'MACD' | 'KDJ' | 'RSI';

export interface MaOverlayIndicator {
  kind: 'MA';
  visible: boolean;
  params: {
    periods: number[];
  };
}

export interface EmaOverlayIndicator {
  kind: 'EMA';
  visible: boolean;
  params: {
    periods: number[];
  };
}

export interface BollOverlayIndicator {
  kind: 'BOLL';
  visible: boolean;
  params: {
    period: number;
    stdDev: number;
  };
}

export type KlineOverlayIndicator = MaOverlayIndicator | EmaOverlayIndicator | BollOverlayIndicator;

export interface KlineIndicatorTemplate {
  id: string;
  name: string;
  scope: 'global';
  source: 'preset' | 'custom';
  version: number;
  overlayIndicators: KlineOverlayIndicator[];
  subIndicator: KlineSubIndicator;
}

export interface SparklineSeries {
  prices: number[];
}

export type WatchlistSparklineMap = Record<string, SparklineSeries>;

export interface StreamEventMap {
  'news.created': NewsItem;
  'news.updated': NewsUpdateEvent;
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
  tier: 'core' | 'watch' | 'muted';
  source: string;
  notes: string | null;
}

export interface XAccountCreatePayload {
  handle: string;
  display_name: string;
  market_focus: string | null;
  is_active: boolean;
  priority: number;
  tier: 'core' | 'watch' | 'muted';
  notes: string | null;
}

export interface XAccountUpdatePayload {
  display_name?: string | null;
  market_focus?: string | null;
  is_active?: boolean;
  priority?: number;
  tier?: 'core' | 'watch' | 'muted';
  notes?: string | null;
}

export interface XAccountsImportResult {
  created_count: number;
  updated_count: number;
  skipped_count: number;
}

export interface XAccountsExportResult {
  exported_count: number;
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

export interface XRadarSignal {
  id: number;
  signal_type: 'account_post' | 'macro_event' | 'multi_account_resonance' | string;
  title: string;
  summary: string;
  market: Market;
  topic_tag: string | null;
  macro_tag: string | null;
  primary_symbol: string | null;
  priority_score: number;
  confidence_score: number;
  source_count: number;
  first_seen_at: string;
  last_seen_at: string;
}

export interface XRadarMacroCluster {
  macro_tag: string;
  title: string;
  signal_count: number;
  source_count: number;
  top_signal_ids: number[];
}

export interface XRadarResponse {
  priority_signals: XRadarSignal[];
  macro_clusters: XRadarMacroCluster[];
  evidence_stream: XPost[];
}

export interface XRefreshResult {
  started_at: string;
  finished_at: string;
  fetched_count: number;
  inserted_count: number;
  error: string | null;
  latency_ms: number;
  skipped: boolean;
  skip_reason: string | null;
  next_refresh_at: string | null;
}

export interface NewsRefreshResult {
  started_at: string;
  finished_at: string;
  fetched_count: number;
  inserted_count: number;
  results: Array<{
    source_name: string;
    source_type: string;
    status: string;
    fetched_count: number;
    inserted_count: number;
    error: string | null;
    latency_ms: number;
  }>;
}

export interface XHealth {
  enabled: boolean;
  configured: boolean;
  healthy: boolean;
  status: string;
  provider_name: string;
  min_interval_seconds: number;
  refresh_cooldown_hours: number;
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

export interface FeishuNotifyConfig {
  configured: boolean;
  app_id: string | null;
  app_secret_set: boolean;
  target_type: string | null;
  target_id: string | null;
  news_enabled: boolean;
  news_keywords: string | null;
  news_batch_interval_minutes: number;
  alert_enabled: boolean;
  analysis_enabled: boolean;
  is_active: boolean;
  updated_at: string | null;
}

export interface FeishuNotifyConfigUpdate {
  app_id: string;
  app_secret?: string;
  target_type: string;
  target_id: string;
  news_enabled: boolean;
  news_keywords?: string | null;
  news_batch_interval_minutes: number;
  alert_enabled: boolean;
  analysis_enabled: boolean;
  is_active: boolean;
}

export interface FeishuTestResult {
  success: boolean;
  message: string;
}
