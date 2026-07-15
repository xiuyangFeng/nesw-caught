import type { NewsItem } from '../../types/api';
import { getNewsDisplayTimestamp } from '../../utils/time';

/**
 * 按小时分桶统计新闻数量,用于绘制迷你趋势线/走势图。
 * 返回长度为 hours 的数组,末位为最近一小时,首位为 hours 小时前。
 */
export function computeHourlyTrend(
  items: NewsItem[],
  hours = 12,
  predicate?: (item: NewsItem) => boolean
): number[] {
  const buckets = new Array<number>(hours).fill(0);
  const now = Date.now();

  for (const item of items) {
    if (predicate && !predicate(item)) {
      continue;
    }
    const rawTimestamp = getNewsDisplayTimestamp(item);
    if (!rawTimestamp) {
      continue;
    }
    const timestamp = new Date(rawTimestamp).getTime();
    if (Number.isNaN(timestamp)) {
      continue;
    }
    const bucketIndex = Math.floor((now - timestamp) / 3_600_000);
    if (bucketIndex >= 0 && bucketIndex < hours) {
      buckets[hours - 1 - bucketIndex] += 1;
    }
  }

  return buckets;
}
