// AI 漏斗（P3）影响判断的展示工具：方向/强度/重要度文案与配色。
// 配色沿用全站 A 股惯例的涨跌色 token（--positive 为“涨”色、--negative 为“跌”色，
// 见 StockCard.vue 的 change_percent 着色）：利多用“涨”色，利空用“跌”色。
import type { ImpactDirection, ImpactStrength, ImpactTargetType } from '../types/api';

export const DIRECTION_LABELS: Record<ImpactDirection, string> = {
  bullish: '利多',
  bearish: '利空',
  neutral: '中性',
};

export const STRENGTH_LABELS: Record<ImpactStrength, string> = {
  strong: '强',
  medium: '中',
  weak: '弱',
};

export const TARGET_TYPE_LABELS: Record<ImpactTargetType, string> = {
  stock: '个股',
  sector: '板块',
};

export const DIRECTION_OPTIONS: ImpactDirection[] = ['bullish', 'bearish', 'neutral'];
export const STRENGTH_OPTIONS: ImpactStrength[] = ['strong', 'medium', 'weak'];
export const TARGET_TYPE_OPTIONS: ImpactTargetType[] = ['stock', 'sector'];

const DIRECTION_TONES: Record<ImpactDirection, string> = {
  bullish: 'border-positive/40 bg-positive/10 text-positive',
  bearish: 'border-negative/40 bg-negative/10 text-negative',
  neutral: 'border-border bg-panel-strong text-muted',
};

export function impactChipText(direction: ImpactDirection, strength: ImpactStrength): string {
  return `${DIRECTION_LABELS[direction] ?? direction}·${STRENGTH_LABELS[strength] ?? strength}`;
}

export function impactChipTone(direction: ImpactDirection): string {
  return DIRECTION_TONES[direction] ?? DIRECTION_TONES.neutral;
}

const IMPORTANCE_LABELS: Record<number, string> = {
  3: '重大',
  2: '重要',
  1: '一般',
  0: '噪音',
};

export function importanceLabel(importance: number): string {
  return IMPORTANCE_LABELS[importance] ?? `重要度 ${importance}`;
}

export function importanceTone(importance: number): string {
  if (importance >= 3) {
    return 'border-danger/40 bg-danger/10 text-danger';
  }
  if (importance === 2) {
    return 'border-warning/40 bg-warning/10 text-warning';
  }
  return 'border-border bg-panel-strong text-muted';
}
