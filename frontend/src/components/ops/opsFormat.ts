/**
 * 运维健康看板（OpsHealthView）子组件共用的纯格式化 / 语义色映射函数。
 *
 * 从 OpsHealthView.vue 组件化拆分而来：原视图内联了这些函数，现下沉到此处
 * 以便被多个 ops/* 卡片组件复用（Workers / Sources / X Sources / LLM 用量 /
 * 系统状态），避免每个组件各自重复实现导致格式漂移。纯函数，不含状态。
 */
import { formatMarketTime } from '../../utils/time';

/** 展示为 "MM/DD HH:mm HKT" 形式的港股时区时间；空值兜底为 "--"。 */
export function timeLabel(iso: string | null | undefined): string {
  if (!iso) {
    return '--';
  }
  return `${formatMarketTime(iso, 'hk')} HKT`;
}

/** 心跳/事件年龄（秒）转为人类可读的相对时间。 */
export function ageLabel(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return '无心跳';
  }
  if (seconds < 60) {
    return `${Math.round(seconds)}s 前`;
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)}m 前`;
  }
  return `${(seconds / 3600).toFixed(1)}h 前`;
}

/** 成功率（0~1 小数）转百分比字符串。 */
export function ratePct(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) {
    return '--';
  }
  return `${(rate * 100).toFixed(1)}%`;
}

/** 平均时延（毫秒）格式化。 */
export function latencyLabel(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) {
    return '--';
  }
  return `${Math.round(ms)}ms`;
}

/** 千分位数字格式化（英文数字分组）。 */
export function numberLabel(value: number): string {
  return value.toLocaleString('en-US');
}

export type OpsTone = 'ok' | 'warning' | 'critical' | 'neutral';

/** worker 状态 -> 语义色。degraded 视为告警橙，ok 绿，其余中性。 */
export function workerTone(status: string): OpsTone {
  if (status === 'ok') {
    return 'ok';
  }
  if (status === 'degraded') {
    return 'warning';
  }
  return 'neutral';
}

/** 数据源（新闻源 / X 源）健康状态 -> 语义色。 */
export function sourceTone(consecutiveFailures: number, disabled: boolean): OpsTone {
  if (disabled) {
    return 'critical';
  }
  if (consecutiveFailures >= 5) {
    return 'warning';
  }
  if (consecutiveFailures > 0) {
    return 'neutral';
  }
  return 'ok';
}
