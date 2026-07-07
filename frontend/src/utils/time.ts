import type { Market } from '../types/api';

interface NewsTimestampCarrier {
  published_at?: string | null;
  fetched_at?: string | null;
}

const MARKET_TIMEZONE: Record<Market, string> = {
  cn: 'Asia/Shanghai',
  hk: 'Asia/Hong_Kong',
  us: 'America/New_York',
};

const MARKET_LABEL: Record<Market, string> = {
  cn: 'CST',
  hk: 'HKT',
  us: 'ET',
};

// 后端 schema 中 market 是普通 string,这里做运行时窄化;
// 未知市场按 us(美东时区)兜底,避免因脏数据抛错。
export function isMarket(value: string | null | undefined): value is Market {
  return value === 'cn' || value === 'hk' || value === 'us';
}

export function normalizeMarket(value: string | null | undefined): Market {
  return isMarket(value) ? value : 'us';
}

function parseUtcDate(utcIso: string): Date {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(utcIso) ? utcIso : `${utcIso}Z`;
  return new Date(normalized);
}

function toEpochMs(utcIso: string | null | undefined): number {
  if (!utcIso) {
    return 0;
  }

  const epochMs = parseUtcDate(utcIso).getTime();
  return Number.isNaN(epochMs) ? 0 : epochMs;
}

export function getNewsDisplayTimestamp(item: NewsTimestampCarrier): string | null {
  return item.published_at ?? item.fetched_at ?? null;
}

export function compareNewsTimestamps(left: NewsTimestampCarrier, right: NewsTimestampCarrier): number {
  return toEpochMs(getNewsDisplayTimestamp(right)) - toEpochMs(getNewsDisplayTimestamp(left));
}

export function formatMarketTime(utcIso: string | null | undefined, market: string): string {
  if (!utcIso) {
    return '--';
  }

  const date = parseUtcDate(utcIso);
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: MARKET_TIMEZONE[normalizeMarket(market)],
  }).format(date);
}

export function getMarketTimezoneLabel(market: string): string {
  return MARKET_LABEL[normalizeMarket(market)];
}

export function minutesSince(utcIso: string | null | undefined): number | null {
  if (!utcIso) {
    return null;
  }
  const diff = Date.now() - toEpochMs(utcIso);
  return Math.max(0, Math.round(diff / 60000));
}

export function isStale(utcIso: string | null | undefined, thresholdMinutes = 5): boolean {
  const minutes = minutesSince(utcIso);
  return minutes === null ? true : minutes > thresholdMinutes;
}
