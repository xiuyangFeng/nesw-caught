import type { SentimentLabel } from '../types/api';

export function formatNumber(value: number | null | undefined, maximumFractionDigits = 2): string {
  if (value === null || value === undefined) {
    return '--';
  }
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits,
  }).format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '--';
  }
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

export function sentimentText(label: SentimentLabel): string {
  const dictionary: Record<SentimentLabel, string> = {
    positive: '偏利好',
    negative: '偏利空',
    neutral: '中性',
    mixed: '分化',
    unknown: '未知',
  };

  return dictionary[label];
}
