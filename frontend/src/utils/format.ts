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

const SENTIMENT_TEXT: Record<SentimentLabel, string> = {
  positive: '偏利好',
  negative: '偏利空',
  neutral: '中性',
  mixed: '分化',
  unknown: '未知',
};

// 后端 schema 中 sentiment_label 是可空的普通 string,这里做运行时窄化,
// 未知取值统一按 unknown 展示。
export function isSentimentLabel(value: string | null | undefined): value is SentimentLabel {
  return (
    value === 'positive' || value === 'negative' || value === 'neutral' || value === 'mixed' || value === 'unknown'
  );
}

export function normalizeSentimentLabel(label: string | null | undefined): SentimentLabel {
  return isSentimentLabel(label) ? label : 'unknown';
}

export function sentimentText(label: string | null | undefined): string {
  return SENTIMENT_TEXT[normalizeSentimentLabel(label)];
}
