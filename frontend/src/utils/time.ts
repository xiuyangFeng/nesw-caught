import type { Market } from '../types/api';

const MARKET_TIMEZONE: Record<Market, string> = {
  hk: 'Asia/Hong_Kong',
  us: 'America/New_York',
};

const MARKET_LABEL: Record<Market, string> = {
  hk: 'HKT',
  us: 'ET',
};

export function formatMarketTime(utcIso: string | null | undefined, market: Market): string {
  if (!utcIso) {
    return '--';
  }

  const date = new Date(utcIso);
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: MARKET_TIMEZONE[market],
  }).format(date);
}

export function getMarketTimezoneLabel(market: Market): string {
  return MARKET_LABEL[market];
}

export function minutesSince(utcIso: string | null | undefined): number | null {
  if (!utcIso) {
    return null;
  }
  const diff = Date.now() - new Date(utcIso).getTime();
  return Math.max(0, Math.round(diff / 60000));
}

export function isStale(utcIso: string | null | undefined, thresholdMinutes = 5): boolean {
  const minutes = minutesSince(utcIso);
  return minutes === null ? true : minutes > thresholdMinutes;
}
