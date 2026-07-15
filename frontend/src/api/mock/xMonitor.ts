// X（Twitter）监控域 mock 数据：抓取健康度、监控账号、原始帖子流、
// 情报雷达(priority_signals/macro_clusters)与刷新结果。

import type { XAccount, XHealth, XPost, XRadarResponse, XRefreshResult } from '../../types/api';
import { isoMinutesAgo, isoMinutesFromNow } from './shared';

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
