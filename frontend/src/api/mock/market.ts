// 行情 + 自选股(watchlist)域 mock 数据：实时快照、自选股列表/候选、K 线、迷你走势、
// 及自选股研究简报(WatchlistResearchBrief)。

import type {
  MarketSnapshot,
  NewsEventMarker,
  SparklineSeries,
  StockKlineResponse,
  StockQuoteDetail,
  WatchlistCandidate,
  WatchlistItem,
  WatchlistQuoteSummary,
  WatchlistResearchBrief,
} from '../../types/api';
import { isoMinutesAgo, now } from './shared';
import { mockNews, mockRelatedNews } from './news';

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
