// 市场总览(market overview)域 mock 数据:五市场聚合总览与指数配置清单。
// 契约见 docs/superpowers/specs/2026-08-02-market-overview-design.md 九节。

import type { MarketIndexConfig, MarketOverview } from '../../types/api';
import { isoMinutesAgo, now } from './shared';

export const mockMarketOverview: MarketOverview = {
  generated_at: now.toISOString(),
  markets: [
    {
      market: 'us',
      display_name: '美股',
      is_open: true,
      indices: [
        {
          symbol: '^GSPC',
          display_name: '标普500',
          kind: 'index',
          price: 6450.12,
          change_percent: 0.82,
          previous_close: 6397.6,
          status: 'ok',
          fetched_at: isoMinutesAgo(1),
        },
        {
          symbol: '^IXIC',
          display_name: '纳斯达克',
          kind: 'index',
          price: 21480.55,
          change_percent: -0.35,
          previous_close: 21556.0,
          status: 'ok',
          fetched_at: isoMinutesAgo(1),
        },
      ],
      quant_sentiment: {
        score: 0.45,
        label: 'greed',
        inputs: { avg_change_percent: 0.24, vix: 14.2, adv_ratio: null },
      },
      boards: {
        status: 'ok',
        stale: false,
        source: 'preset_etf',
        items: [
          { code: 'XLK', name: '科技ETF', change_percent: 1.2 },
          { code: 'XLE', name: '能源ETF', change_percent: -0.6 },
          { code: 'XLF', name: '金融ETF', change_percent: 0.4 },
        ],
      },
      news_sentiment: {
        status: 'ok',
        score: 0.31,
        sample_count: 12,
        top_signals: [
          {
            news_id: 101,
            title: 'Fed officials signal patience on rate path',
            summary: '多位美联储官员暗示不急于调整利率路径。',
            signal_confidence: 0.9,
            source_name: 'Reuters',
            published_at: isoMinutesAgo(90),
            canonical_url: 'https://example.com/news/101',
          },
          {
            news_id: 102,
            title: 'Megacap earnings lift Nasdaq breadth',
            summary: '大型科技股财报整体超预期。',
            signal_confidence: 0.82,
            source_name: 'CNBC',
            published_at: isoMinutesAgo(240),
            canonical_url: 'https://example.com/news/102',
          },
        ],
      },
    },
    {
      market: 'cn',
      display_name: 'A股',
      is_open: false,
      indices: [
        {
          symbol: '000300.SS',
          display_name: '沪深300',
          kind: 'index',
          price: 4012.35,
          change_percent: -0.48,
          previous_close: 4031.72,
          status: 'ok',
          fetched_at: isoMinutesAgo(30),
        },
        {
          symbol: '000001.SS',
          display_name: '上证指数',
          kind: 'index',
          price: 3255.1,
          change_percent: 0.12,
          previous_close: 3251.2,
          status: 'ok',
          fetched_at: isoMinutesAgo(30),
        },
      ],
      quant_sentiment: {
        score: -0.1,
        label: 'neutral',
        inputs: { avg_change_percent: -0.18, vix: null, adv_ratio: 0.46 },
      },
      boards: {
        status: 'ok',
        stale: false,
        source: 'eastmoney',
        items: [
          { code: 'BK0420', name: '航天航空', change_percent: 2.35 },
          { code: 'BK0737', name: '软件开发', change_percent: 1.86 },
          { code: 'BK0475', name: '银行', change_percent: -0.92 },
        ],
      },
      news_sentiment: {
        status: 'ok',
        score: -0.12,
        sample_count: 8,
        top_signals: [
          {
            news_id: 201,
            title: '国常会部署新一轮稳增长举措',
            summary: '会议指出要加大宏观政策调节力度。',
            signal_confidence: 0.88,
            source_name: '新华财经',
            published_at: isoMinutesAgo(300),
            canonical_url: 'https://example.com/news/201',
          },
        ],
      },
    },
    {
      market: 'kr',
      display_name: '韩国',
      is_open: false,
      indices: [
        {
          symbol: '^KS11',
          display_name: '韩国KOSPI',
          kind: 'index',
          price: 2620.4,
          change_percent: 0.55,
          previous_close: 2606.06,
          status: 'ok',
          fetched_at: isoMinutesAgo(120),
        },
      ],
      quant_sentiment: {
        score: 0.12,
        label: 'neutral',
        inputs: { avg_change_percent: 0.55, vix: null, adv_ratio: null },
      },
      boards: { status: 'none', stale: false, source: 'none', items: [] },
      news_sentiment: { status: 'insufficient_data', score: null, sample_count: 0, top_signals: [] },
    },
    {
      market: 'jp',
      display_name: '日本',
      is_open: false,
      indices: [
        {
          symbol: '^N225',
          display_name: '日经225',
          kind: 'index',
          price: 39850.2,
          change_percent: -1.05,
          previous_close: 40273.5,
          status: 'ok',
          fetched_at: isoMinutesAgo(150),
        },
      ],
      quant_sentiment: {
        score: -0.5,
        label: 'fear',
        inputs: { avg_change_percent: -1.05, vix: null, adv_ratio: null },
      },
      boards: { status: 'none', stale: false, source: 'none', items: [] },
      news_sentiment: { status: 'insufficient_data', score: null, sample_count: 1, top_signals: [] },
    },
    {
      market: 'eu',
      display_name: '欧洲',
      is_open: true,
      indices: [
        {
          symbol: '^STOXX50E',
          display_name: '欧洲斯托克50',
          kind: 'index',
          price: 4950.6,
          change_percent: 0.34,
          previous_close: 4933.8,
          status: 'ok',
          fetched_at: isoMinutesAgo(5),
        },
        {
          symbol: '^GDAXI',
          display_name: '德国DAX',
          kind: 'index',
          price: 18320.4,
          change_percent: 0.41,
          previous_close: 18245.6,
          status: 'ok',
          fetched_at: isoMinutesAgo(5),
        },
      ],
      quant_sentiment: {
        score: 0.3,
        label: 'greed',
        inputs: { avg_change_percent: 0.38, vix: null, adv_ratio: null },
      },
      boards: {
        status: 'ok',
        stale: false,
        source: 'preset_etf',
        items: [{ code: 'FEZ', name: '欧洲蓝筹ETF', change_percent: 0.5 }],
      },
      news_sentiment: { status: 'insufficient_data', score: null, sample_count: 2, top_signals: [] },
    },
  ],
};

export const mockMarketIndexConfigs: MarketIndexConfig[] = [
  { id: 1, symbol: '^GSPC', market: 'us', display_name: '标普500', kind: 'index', sort_order: 0, enabled: true },
  { id: 2, symbol: '^IXIC', market: 'us', display_name: '纳斯达克', kind: 'index', sort_order: 1, enabled: true },
  { id: 3, symbol: '^VIX', market: 'us', display_name: '恐慌指数', kind: 'index', sort_order: 2, enabled: true },
  { id: 4, symbol: 'XLK', market: 'us', display_name: '科技ETF', kind: 'etf', sort_order: 3, enabled: true },
  { id: 5, symbol: '000300.SS', market: 'cn', display_name: '沪深300', kind: 'index', sort_order: 0, enabled: true },
  { id: 6, symbol: '000001.SS', market: 'cn', display_name: '上证指数', kind: 'index', sort_order: 1, enabled: true },
  { id: 7, symbol: '^KS11', market: 'kr', display_name: '韩国KOSPI', kind: 'index', sort_order: 0, enabled: true },
  { id: 8, symbol: '^N225', market: 'jp', display_name: '日经225', kind: 'index', sort_order: 0, enabled: true },
  { id: 9, symbol: '^STOXX50E', market: 'eu', display_name: '欧洲斯托克50', kind: 'index', sort_order: 0, enabled: true },
  { id: 10, symbol: '^GDAXI', market: 'eu', display_name: '德国DAX', kind: 'index', sort_order: 1, enabled: true },
  { id: 11, symbol: 'FEZ', market: 'eu', display_name: '欧洲蓝筹ETF', kind: 'etf', sort_order: 2, enabled: false },
];
