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

// 前端 UI 专用:POST /api/news/refresh?async_mode=true 分支返回的是手工拼装的
// JSONResponse({"status": "accepted", "message": ...}),不是 response_model
// 声明的 NewsRefreshResponse(那是同步分支的形状),OpenAPI 不覆盖,手写。
export interface NewsRefreshAcceptedResult {
  status: string;
  message: string;
}

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
export type LLMStats = Schemas['LLMStatsView'];

// ---------------------------------------------------------------------------
// 行情 / 自选股
// ---------------------------------------------------------------------------
export type MarketSnapshot = Schemas['PriceSnapshotView'];
export type WatchlistQuoteSummary = Schemas['QuoteSummaryView'];
export type StockQuoteDetail = Schemas['QuoteDetailView'];
// 说明:后端 WatchlistItemView 已新增 position_size / average_cost(持仓/组合视图),
// 但尚未纳入 generate:api 的 OpenAPI 快照(src/types/generated/api.d.ts),此处用交叉
// 类型补齐;待运行 `npm run generate:api` 后可移除本增补,退回纯别名。
export type WatchlistItem = Schemas['WatchlistItemView'] & {
  position_size?: number | null;
  average_cost?: number | null;
};
export type WatchlistItemCreate = Schemas['WatchlistItemCreate'];
export type WatchlistCandidate = Schemas['WatchlistCandidateView'];
export type MarketRefreshResult = Schemas['MarketRefreshResultView'];

export type WatchlistResearchDriver = Schemas['WatchlistResearchDriverView'];
export type WatchlistResearchBrief = Schemas['WatchlistResearchBriefView'];
export type ResearchDriverCategory = WatchlistResearchDriver['category'];
export type ResearchActionLevel = WatchlistResearchDriver['action_level'];
export type ResearchTopActionLevel = WatchlistResearchBrief['top_action_level'];

// 个股 AI 综合研判（本地语料 RAG，结构化研报）
export type StockResearchReport = Schemas['StockResearchReport'];
export type StockResearchKeyEvent = Schemas['StockResearchKeyEvent'];
export type StockResearchReference = Schemas['StockResearchReference'];
export type StockResearchPriceContext = Schemas['StockResearchPriceContext'];
export type StockResearchRating = StockResearchReport['overall_rating'];

export type WatchlistAiInsight = Schemas['WatchlistAiInsightView'];

// ---------------------------------------------------------------------------
// 持仓 / 组合视图（Portfolio）
// 说明:后端新增 /api/portfolio 接口(app/schemas/portfolio.py)尚未纳入
// generate:api 的 OpenAPI 快照,此处按后端 schema 手写镜像;待运行
// `npm run generate:api` 后可替换为 Schemas 别名。
// ---------------------------------------------------------------------------
export interface PortfolioPosition {
  symbol: string;
  market: string;
  display_name: string;
  position_size: number;
  average_cost: number | null;
  current_price: number | null;
  change_percent: number | null;
  price_status: string;
  price_message: string | null;
  quote_fetched_at: string | null;
  market_value: number | null;
  cost_basis: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_percent: number | null;
  weight: number | null;
}

export interface PortfolioWeightedNews {
  news_item: NewsItem;
  symbols: string[];
  sentiment_score: number | null;
  signed_impact: number;
  impact_score: number;
}

export interface PortfolioSummary {
  generated_at: string;
  position_count: number;
  priced_position_count: number;
  total_market_value: number;
  total_cost_basis: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_percent: number | null;
  positions: PortfolioPosition[];
  weighted_news: PortfolioWeightedNews[];
}

// 写入持仓量 / 平均成本的更新载荷(对应后端 WatchlistItemUpdate)。
export interface WatchlistPositionUpdate {
  position_size?: number | null;
  average_cost?: number | null;
}

// ---------------------------------------------------------------------------
// 市场总览（Market Overview）
// C1 联调(2026-08-02)后统一以 generated 类型为准,仅保留两类增补:
//   1. 后端 schema 中 market/kind/label/source 为普通 string,以下窄化联合
//      仅用于前端表单/展示的 UI 状态,不代表后端契约;
//   2. 后端 pydantic 字段带默认值(list default_factory / None)时 generated
//      会标成可选(?),但契约(设计文档九节)保证字段始终下发,用交叉类型
//      恢复必填,避免组件到处写 `?? []`。
// ---------------------------------------------------------------------------
export type MarketOverviewMarketKey = 'us' | 'cn' | 'kr' | 'jp' | 'eu';
export type MarketIndexKind = 'index' | 'etf';
export type QuantSentimentLabel = 'panic' | 'fear' | 'neutral' | 'greed' | 'greed_extreme' | 'unknown';
export type MarketBoardSource = 'eastmoney' | 'preset_etf' | 'none';

export type OverviewIndexQuote = Schemas['OverviewIndexQuoteView'];
export type QuantSentimentInputs = Schemas['QuantSentimentInputsView'];
export type QuantSentiment = Schemas['QuantSentimentView'];
export type MarketBoardItem = Schemas['BoardItemView'];
export type MarketBoardSection = Schemas['BoardSectionView'] & {
  // 契约保证 items 始终为数组(后端 default_factory=list)。
  items: MarketBoardItem[];
};
export type MarketNewsSignalItem = Schemas['NewsSignalItemView'];
export type MarketNewsSentiment = Schemas['NewsSentimentView'];
export type MarketOverviewMarket = Schemas['MarketOverviewMarketView'] & {
  // 契约保证以下字段始终下发(后两者可为 null),generated 因后端默认值标成可选。
  indices: OverviewIndexQuote[];
  quant_sentiment: QuantSentiment | null;
  boards: MarketBoardSection;
  news_sentiment: MarketNewsSentiment | null;
};
export type MarketOverview = Omit<Schemas['MarketOverviewView'], 'markets'> & {
  markets: MarketOverviewMarket[];
};

export type MarketIndexConfig = Schemas['MarketIndexConfigView'];
// kind/sort_order/enabled 后端有默认值、客户端可省略;generated 把带默认值的
// 字段标成必填,此处按真实线上契约放宽为可选。
export type MarketIndexConfigCreate = Omit<
  Schemas['MarketIndexConfigCreateRequest'],
  'kind' | 'sort_order' | 'enabled'
> &
  Partial<Pick<Schemas['MarketIndexConfigCreateRequest'], 'kind' | 'sort_order' | 'enabled'>>;
// PATCH 契约不允许修改 symbol / market(后端 extra="forbid",显式传入直接 422)。
export type MarketIndexConfigUpdate = Schemas['MarketIndexConfigUpdateRequest'];
// 前端 UI 专用:后端 WatchlistAiInsightView.failover 在 schema 中是无结构的
// dict[str, str],此接口是前端对其约定字段的窄化描述,仅供展示层使用。
export interface LlmFailoverInfo {
  from_model: string;
  to_model: string;
  reason: string;
}

// ---------------------------------------------------------------------------
// 财报 / 事件日历
// ---------------------------------------------------------------------------
export type CalendarEventType = 'earnings' | 'ex_dividend';
export type CalendarEvent = Schemas['CalendarEventView'];
export type CalendarSymbolSummary = Schemas['CalendarSymbolSummaryView'];
export type CalendarResponse = Schemas['CalendarResponseView'];

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
// 运维健康看板(Ops Health Dashboard)
// ---------------------------------------------------------------------------
export type OpsHealth = Schemas['OpsHealthResponse'];
export type OpsAlert = Schemas['OpsAlert'];
export type OpsWorker = Schemas['OpsWorkerView'];
export type OpsSource = Schemas['OpsSourceView'];
export type OpsXSource = Schemas['OpsXSourceView'];
export type OpsLlmUsage = Schemas['OpsLlmUsageView'];
export type OpsLlmModelUsage = Schemas['OpsLlmModelUsageView'];
export type OpsEventBus = Schemas['OpsEventBusView'];
export type OpsDatabase = Schemas['OpsDatabaseView'];

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
  // MarketQuoteProducer 每轮刷新后发布，是自选股行情的推送通道
  // （后端 STREAM_EVENT_NAMES 与 app/services/market_quote_producer.py 对齐）。
  // quotes 来自 QuoteService._snapshot_to_payload，字段与 PriceSnapshotView 同构
  // （比 QuoteSummaryView 多 is_abnormal / abnormal_reason），因此用 MarketSnapshot。
  'market.watchlist_refreshed': { symbols: string[]; quotes: MarketSnapshot[] };
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
// 信号有效性回测（Signal Backtest）
// ---------------------------------------------------------------------------
// Pydantic 为带默认值的字段生成了 required OpenAPI 属性，但前端仍需兼容部署升级前
// 的旧响应，因此只把这 3 个 additive 字段放宽为可选；其余结构直接跟随生成契约。
type GeneratedBacktestSummary = Schemas['BacktestSummaryView'];
export type BacktestSummary = Omit<
  GeneratedBacktestSummary,
  'benchmark_note' | 'distinct_news_count' | 'skipped_stale_count'
> & {
  benchmark_note?: GeneratedBacktestSummary['benchmark_note'];
  distinct_news_count?: GeneratedBacktestSummary['distinct_news_count'];
  skipped_stale_count?: GeneratedBacktestSummary['skipped_stale_count'];
};
export type SignalDirectionStats = Schemas['SignalDirectionStatsView'];
export type ImportanceBucketStats = Schemas['ImportanceBucketStatsView'];

// 前端 UI 专用:回测查询表单状态,理由同 NewsQuery(market 含 '' 哨兵值)。
export type BacktestQuery = {
  market?: Market | '';
  window_days?: number;
  horizon?: string;
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

// ---------------------------------------------------------------------------
// 每日盘前/盘后 AI 简报（Daily Digest）
// ---------------------------------------------------------------------------
export type DigestSection = Schemas['DigestSectionView'];
export type Digest = Schemas['DigestView'];
export type DigestLatest = Schemas['DigestLatestView'];
// 情绪/利好利空评测与 Phase 2/3 类型已在本次集成后进入 OpenAPI，统一回归生成类型。
// ---------------------------------------------------------------------------
export type SentimentEvalLabel = 'positive' | 'negative' | 'neutral';
export type SentimentLabelMetrics = Schemas['SentimentLabelMetrics'];
export type SentimentEvaluationMetrics = Schemas['SentimentEvaluationMetrics'];
export type SentimentModelRun = Schemas['SentimentModelRun'];
export type SentimentLabelDelta = Schemas['SentimentLabelDelta'];
export type SentimentABComparison = Schemas['SentimentABComparison'];
export type SentimentEvalHistoryPoint = Schemas['SentimentEvalHistoryPoint'];
export type SentimentEvalRegression = Schemas['SentimentEvalRegression'];
export type SentimentEvalResponse = Schemas['SentimentEvalResponse'];

// 后端 sentiment_label 是普通可空 string；前端只在已知三种标签上着色，因此窄化。
export type SentimentTimelineNewsRef = Omit<
  Schemas['SentimentTimelineNewsItemView'],
  'sentiment_label'
> & {
  sentiment_label?: SentimentEvalLabel | null;
};
export type SentimentTimelinePoint = Omit<Schemas['SentimentTimelinePointView'], 'top_news'> & {
  top_news: SentimentTimelineNewsRef[];
};
export type DivergenceStatus = Schemas['SentimentDivergenceView'];
export type DivergenceStatusValue = DivergenceStatus['status'];
export type SentimentTimelineResponse = Omit<
  Schemas['SentimentTimelineView'],
  'points' | 'divergence'
> & {
  points: SentimentTimelinePoint[];
  divergence: DivergenceStatus | null;
};

export type ScoreBucketStats = Schemas['ScoreBucketStatsView'];
export type CalibrationMappingEntry = Schemas['CalibrationMappingEntryView'];
export type SentimentCalibration = Schemas['SentimentCalibrationView'];
