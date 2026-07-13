/**
 * API 类型适配层。
 *
 * 所有与后端 HTTP API 对应的类型一律从 `src/types/generated/api.d.ts`
 * (由 `npm run generate:api` 从 FastAPI OpenAPI schema 自动生成)取别名,
 * 保持既有导入路径与导出名不变;禁止在本文件手写与后端重复的结构。
 *
 * 仅以下两类允许保留手写定义,且每处必须注释原因:
 *   1. SSE 带内协议(/api/stream/events 的事件信封),OpenAPI 不覆盖;
 *   2. 前端 UI 专用类型(视图态、本地持久化、查询表单状态等)。
 */
import type { components, operations } from './generated/api';

type Schemas = components['schemas'];

// ---------------------------------------------------------------------------
// 前端 UI 专用:后端 schema 中 market / sentiment 等字段为普通 string,
// 以下窄化联合仅用于前端筛选表单、路由参数等 UI 状态,不代表后端契约。
// ---------------------------------------------------------------------------
export type Market = 'hk' | 'us' | 'cn';
export type SentimentLabel = 'positive' | 'negative' | 'neutral' | 'mixed' | 'unknown';
export type ExtractStatus = 'pending' | 'success' | 'failed' | 'not_requested';

// ---------------------------------------------------------------------------
// Health / 运行时状态
// ---------------------------------------------------------------------------
export type HealthStatus = Schemas['HealthResponse'];
export type NewsRuntimeSource = Schemas['NewsRuntimeSourceView'];
export type NewsRuntimeMarket = Schemas['NewsRuntimeMarketView'];
export type NewsRuntimeStatus = Schemas['NewsRuntimeView'];

// ---------------------------------------------------------------------------
// 新闻
// ---------------------------------------------------------------------------
export type NewsItem = Schemas['NewsItemSummary'];
export type NewsMention = Schemas['NewsMentionView'];
export type NewsTopicRef = Schemas['NewsTopicRefView'];
export type NewsArticle = Schemas['NewsArticleView'];
export type NewsDetail = Schemas['NewsDetailView'];
export type NewsFeedEventCard = Schemas['NewsFeedEventCardView'];
export type NewsEventDetail = Schemas['NewsEventDetailView'];
export type NewsFeedTopic = Schemas['NewsFeedTopicView'];
export type NewsFeedLayout = Schemas['NewsFeedLayoutView'];
export type NewsListPage = Schemas['NewsListPageView'];
export type NewsRefreshResult = Schemas['NewsRefreshResponse'];

// SSE 带内协议:news.updated 事件负载在 NewsItemSummary 之上附加
// updated_fields,由 stream 路由手工组装,OpenAPI 不覆盖。
export interface NewsUpdateEvent extends NewsItem {
  updated_fields: string[];
}

// ---------------------------------------------------------------------------
// LLM 配置与分析
// ---------------------------------------------------------------------------
export type LLMConfigSummary = Schemas['LLMConfigView'];
export type LLMConfigUpdateRequest = Schemas['LLMConfigUpsertRequest'];
export type LLMTranslateRequest = Schemas['LLMTranslateRequest'];
export type LLMTranslateResponse = Schemas['LLMTranslateView'];
export type LLMConnectionTestResponse = Schemas['LLMConnectionTestView'];
export type NewsAnalysisCandidate = Schemas['LLMAnalysisCandidate'];
export type NewsAnalysis = Schemas['NewsAnalysisView'];

// ---------------------------------------------------------------------------
// 行情 / 自选股
// ---------------------------------------------------------------------------
export type MarketSnapshot = Schemas['PriceSnapshotView'];
export type WatchlistQuoteSummary = Schemas['QuoteSummaryView'];
export type StockQuoteDetail = Schemas['QuoteDetailView'];
export type WatchlistItem = Schemas['WatchlistItemView'];
export type WatchlistItemCreate = Schemas['WatchlistItemCreate'];
export type WatchlistCandidate = Schemas['WatchlistCandidateView'];
export type MarketRefreshResult = Schemas['MarketRefreshResultView'];

export type WatchlistResearchDriver = Schemas['WatchlistResearchDriverView'];
export type WatchlistResearchBrief = Schemas['WatchlistResearchBriefView'];
export type ResearchDriverCategory = WatchlistResearchDriver['category'];
export type ResearchActionLevel = WatchlistResearchDriver['action_level'];
export type ResearchTopActionLevel = WatchlistResearchBrief['top_action_level'];

export type WatchlistAiInsight = Schemas['WatchlistAiInsightView'];
// 前端 UI 专用:后端 WatchlistAiInsightView.failover 在 schema 中是无结构的
// dict[str, str],此接口是前端对其约定字段的窄化描述,仅供展示层使用。
export interface LlmFailoverInfo {
  from_model: string;
  to_model: string;
  reason: string;
}

// ---------------------------------------------------------------------------
// 话题
// ---------------------------------------------------------------------------
export type TopicItem = Schemas['TopicItemView'];
export type TopicDetail = Schemas['TopicDetailView'];

// ---------------------------------------------------------------------------
// Stream 状态(REST 部分)
// ---------------------------------------------------------------------------
export type StreamStatus = Schemas['StreamStatusResponse'];
export type MarketWorkerStatus = Schemas['MarketWorkerStatusView'];

// ---------------------------------------------------------------------------
// K 线
// ---------------------------------------------------------------------------
export type KlineCandle = Schemas['CandlePointView'];
export type KlineValuePoint = Schemas['ValuePointView'];
export type KlineMacdPoint = Schemas['MacdPointView'];
export type KlineKdjPoint = Schemas['KdjPointView'];
export type KlineBollingerPoint = Schemas['BollingerPointView'];
export type NewsEventMarkerItem = Schemas['NewsEventItemView'];
export type NewsEventMarker = Schemas['NewsEventGroupView'];
export type KlineIndicators = Schemas['IndicatorSeriesView'];
export type StockKlineResponse = Schemas['MarketKlineView'];

// ---------------------------------------------------------------------------
// Sparkline
// ---------------------------------------------------------------------------
export type SparklineSeries = Schemas['SparklineSeriesView'];
export type WatchlistSparklineMap =
  operations['get_watchlist_sparklines_api_market_sparklines_post']['responses']['200']['content']['application/json'];

// ---------------------------------------------------------------------------
// 前端 UI 专用:自选股仪表盘周期切换的视图态。
// ---------------------------------------------------------------------------
export type WatchlistDashboardPeriod = '1D' | '1W' | '1M' | '1Y';

// ---------------------------------------------------------------------------
// 前端 UI 专用:K 线画图工具的本地状态与 localStorage 持久化结构,
// 纯前端能力,后端无对应 API。
// ---------------------------------------------------------------------------
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

// 前端 UI 专用:本地持久化通用信封(localStorage 版本迁移用)。
export interface VersionedPersistedValue<T> {
  version: number;
  savedAt: string;
  payload: T;
}

// ---------------------------------------------------------------------------
// 前端 UI 专用:K 线指标工作台的模板/叠加指标视图态,纯前端配置。
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// SSE 带内协议:/api/stream/events 是 text/event-stream,事件信封与
// 事件负载映射不在 OpenAPI 内,以下手写定义与后端 stream 路由约定对齐。
// ---------------------------------------------------------------------------
export interface StreamEventMap {
  'news.created': NewsItem;
  'news.updated': NewsUpdateEvent;
  'topic.updated': Pick<TopicItem, 'id' | 'topic_title' | 'market' | 'importance_score' | 'news_count' | 'last_seen_at'>;
  'watchlist.movement': MarketSnapshot;
  'stream.keepalive': { status: 'ok' };
}

export type StreamEventType = keyof StreamEventMap;

// Distributive over StreamEventType so `envelope.type === 'news.created'`
// narrows `envelope.payload` like a discriminated union.
export type StreamEnvelope<T extends StreamEventType = StreamEventType> = T extends StreamEventType
  ? {
      type: T;
      occurred_at: string;
      payload: StreamEventMap[T];
    }
  : never;

// ---------------------------------------------------------------------------
// 前端 UI 专用:GET 查询参数的表单状态(含 '' 空选项哨兵值),
// 与 OpenAPI 的 query parameters 并非同构,保留手写。
// Type alias (not interface) so it satisfies the index-signature constraint of
// query-string helpers like withQuery.
// ---------------------------------------------------------------------------
export type NewsQuery = {
  market?: Market | '';
  q?: string;
  source_name?: string;
  sentiment_label?: SentimentLabel | '';
  limit?: number;
  cursor?: string;
};

// ---------------------------------------------------------------------------
// X 监控
// ---------------------------------------------------------------------------
export type XAccount = Schemas['XAccountView'];
export type XAccountCreatePayload = Schemas['XAccountCreateRequest'];
export type XAccountUpdatePayload = Schemas['XAccountUpdateRequest'];
export type XAccountsImportResult = Schemas['XAccountsImportResult'];
export type XAccountsExportResult = Schemas['XAccountsExportResult'];
export type XPost = Schemas['XPostSummaryView'];
export type XRadarSignal = Schemas['XRadarSignalView'];
export type XRadarMacroCluster = Schemas['XRadarMacroClusterView'];
export type XRadarResponse = Schemas['XRadarResponse'];
export type XRefreshResult = Schemas['XRefreshResponse'];
export type XHealth = Schemas['XHealthResponse'];

// 前端 UI 专用:X 帖子查询表单状态(含 '' 哨兵值),理由同 NewsQuery。
export type XPostQuery = {
  account_handle?: string;
  market?: Market | '';
  q?: string;
  symbol?: string;
  limit?: number;
};

// ---------------------------------------------------------------------------
// 飞书通知
// ---------------------------------------------------------------------------
// 告警治理配置。后端以 settings 默认 + NotificationService 内存覆盖实现（不落库），
// 通过既有飞书配置接口回显 / 保存。generated/api.d.ts 暂未含该字段，这里 additive 扩展。
export type AlertGovernanceConfig = {
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  quiet_hours_tz: string;
  dedupe_window_minutes: number;
  digest_window_minutes: number;
  digest_threshold: number;
  critical_change_percent: number;
};

export type FeishuNotifyConfig = Schemas['FeishuConfigView'] & {
  governance?: AlertGovernanceConfig | null;
};
export type FeishuNotifyConfigUpdate = Schemas['FeishuConfigUpsertRequest'] & {
  governance?: Partial<AlertGovernanceConfig> | null;
};
export type FeishuTestResult = Schemas['FeishuTestResult'];
