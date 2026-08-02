// 运维/系统域 mock 数据：后端健康检查、SSE 流状态与事件、飞书通知配置/测试结果、
// 以及新闻抓取链路运行时状态(NewsRuntimeStatus，各市场/信源的健康度)。

import type {
  FeishuNotifyConfig,
  FeishuTestResult,
  HealthStatus,
  NewsRuntimeStatus,
  StreamEnvelope,
  StreamStatus,
} from '../../types/api';
import { isoMinutesAgo, now } from './shared';

export const mockHealth: HealthStatus = {
  status: 'ok',
  app_name: 'News Caught Backend',
  environment: 'development',
  now_utc: now.toISOString(),
  database: 'configured',
  database_healthy: true,
  active_stream_connections: 0,
  stream_mode: 'sse',
  ai_enabled: false,
  ai_status: { enabled: false, last_call_at: null },
  source_health_summary: { total: 0, disabled: 0, consecutive_failing: 0 },
  x_monitor_enabled: false,
  x_monitor_healthy: false,
};

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
