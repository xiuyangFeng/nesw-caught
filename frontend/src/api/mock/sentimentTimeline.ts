// 个股情绪时间线 + 情绪-价格背离（工作块 G，后端并行开发中）mock 数据：
// GET /api/watchlist/{symbol}/sentiment-timeline?days= 的离线/降级夹具。
//
// 覆盖设计文档 docs/superpowers/specs/2026-08-02-sentiment-phase2-3-design.md 「G1/G2」
// 要求的三态：背离（bearish/bullish 各一例）、无背离（有时间线但 divergence=null）、
// 空数据（无相关新闻，points=[] 且 divergence=null，作为未在夹具表中收录 symbol 的兜底）。

import type { DivergenceStatus, SentimentTimelineNewsRef, SentimentTimelinePoint, SentimentTimelineResponse } from '../../types/api';
import { isoMinutesAgo, now } from './shared';

function dateDaysAgo(days: number): string {
  return new Date(now.getTime() - days * 86_400_000).toISOString().slice(0, 10);
}

function newsRef(id: number, title: string, score: number): SentimentTimelineNewsRef {
  return {
    id,
    title,
    sentiment_score: score,
    sentiment_label: score > 0.15 ? 'positive' : score < -0.15 ? 'negative' : 'neutral',
  };
}

let nextNewsId = 9001;

function buildPoint(daysAgo: number, avgScore: number, newsCount: number, topTitles: string[]): SentimentTimelinePoint {
  const topNews = topTitles.map((title, index) => newsRef(nextNewsId++, title, avgScore + (index === 0 ? 0.05 : -0.05 * index)));
  const positive_count = topNews.filter((n) => n.sentiment_label === 'positive').length;
  const negative_count = topNews.filter((n) => n.sentiment_label === 'negative').length;
  const neutral_count = Math.max(newsCount - positive_count - negative_count, 0);
  return {
    date: dateDaysAgo(daysAgo),
    avg_score: avgScore,
    news_count: newsCount,
    positive_count,
    negative_count,
    neutral_count,
    top_news: topNews,
  };
}

// AAPL：情绪偏多但价格走弱 -> bearish_divergence（红色警示）。
const aaplPoints: SentimentTimelinePoint[] = [
  buildPoint(6, 0.28, 4, ['苹果新品发布会临近，供应链排产超预期']),
  buildPoint(5, 0.35, 6, ['分析师上调苹果目标价，看好服务业务增长', '苹果与供应商签订新一轮长期协议']),
  buildPoint(3, 0.41, 5, ['苹果季度指引乐观，市场情绪偏多']),
  buildPoint(1, 0.3, 3, ['苹果零售渠道数据向好']),
];

const aaplDivergence: DivergenceStatus = {
  status: 'bearish_divergence',
  window_days: 7,
  sentiment_avg: 0.34,
  news_count: 18,
  price_change_percent: -3.8,
  detected_at: isoMinutesAgo(30),
};

// 0700.HK：情绪偏空但价格走强 -> bullish_divergence（绿色，反向文案）。
const tencentPoints: SentimentTimelinePoint[] = [
  buildPoint(6, -0.22, 3, ['监管趋严传闻扰动腾讯游戏板块情绪']),
  buildPoint(4, -0.31, 5, ['市场担忧腾讯广告收入放缓', '海外游戏发行进度不及预期']),
  buildPoint(2, -0.18, 2, ['行业竞争加剧，情绪偏谨慎']),
];

const tencentDivergence: DivergenceStatus = {
  status: 'bullish_divergence',
  window_days: 7,
  sentiment_avg: -0.24,
  news_count: 10,
  price_change_percent: 4.1,
  detected_at: isoMinutesAgo(45),
};

// NVDA：有正常时间线数据，但情绪与价格同向 -> 无背离（divergence=null）。
const nvdaPoints: SentimentTimelinePoint[] = [
  buildPoint(7, 0.18, 3, ['英伟达新一代芯片订单强劲']),
  buildPoint(5, -0.12, 2, ['部分客户交付延迟引发短期担忧']),
  buildPoint(4, 0.25, 4, ['数据中心需求持续超预期', 'AI 算力扩产计划落地']),
  buildPoint(2, 0.08, 2, ['情绪转向中性，等待财报']),
  buildPoint(0, 0.15, 3, ['财报前瞻偏乐观']),
];

export const mockSentimentTimelines: Record<string, SentimentTimelineResponse> = {
  AAPL: { symbol: 'AAPL', days: 30, points: aaplPoints, divergence: aaplDivergence },
  '0700.HK': { symbol: '0700.HK', days: 30, points: tencentPoints, divergence: tencentDivergence },
  NVDA: { symbol: 'NVDA', days: 30, points: nvdaPoints, divergence: null },
};

/** 未在夹具表中收录的 symbol 一律兜底为「空数据」态：无相关新闻，divergence 也为 null。 */
export function buildMockSentimentTimeline(symbol: string, days = 30): SentimentTimelineResponse {
  return { symbol, days, points: [], divergence: null };
}
