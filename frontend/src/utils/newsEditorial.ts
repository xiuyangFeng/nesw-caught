import type { NewsDetail, NewsItem } from '../types/api';
import { getNewsBody, getNewsSummary } from './news';
import { compareNewsTimestamps, getNewsDisplayTimestamp } from './time';

export interface EditorialStoryEntry {
  item: NewsItem;
  detail: NewsDetail | null;
  score: number;
}

export interface EditorialStoryGroup {
  lead: EditorialStoryEntry | null;
  supporting: EditorialStoryEntry[];
  stream: EditorialStoryEntry[];
}

interface GroupOptions {
  supportingCount?: number;
}

const HOUR_MS = 60 * 60 * 1000;

function getFreshnessScore(item: NewsItem): number {
  const publishedMs = Date.parse(getNewsDisplayTimestamp(item) ?? '');
  if (Number.isNaN(publishedMs)) {
    return 0;
  }

  const ageHours = Math.max(0, (Date.now() - publishedMs) / HOUR_MS);
  return Math.max(0, 24 - ageHours) / 24;
}

function getDetailQualityScore(item: NewsItem, detail: NewsDetail | null): number {
  let score = 0;

  if (getNewsSummary(item)) {
    score += 0.16;
  }
  if (detail?.topic) {
    score += 0.14;
  }
  if (detail?.mentions.length) {
    score += Math.min(0.12, detail.mentions.length * 0.03);
  }
  if (detail && getNewsSummary(detail)) {
    score += 0.08;
  }
  if (detail && getNewsBody(detail)) {
    score += 0.12;
  }

  return score;
}

export function getEditorialScore(item: NewsItem, detail: NewsDetail | null): number {
  const importance = detail?.topic?.importance_score ?? 0;
  const freshness = getFreshnessScore(item);
  const quality = getDetailQualityScore(item, detail);
  const detailPenalty = detail ? 0 : -0.08;

  return importance * 0.58 + freshness * 0.26 + quality + detailPenalty;
}

export function rankEditorialStories(
  items: NewsItem[],
  detailMap: Record<number, NewsDetail | null>,
): EditorialStoryEntry[] {
  return [...items]
    .map((item) => ({
      item,
      detail: detailMap[item.id] ?? null,
      score: getEditorialScore(item, detailMap[item.id] ?? null),
    }))
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }

      const timeDiff = compareNewsTimestamps(left.item, right.item);
      if (timeDiff !== 0) {
        return timeDiff;
      }

      return right.item.id - left.item.id;
    });
}

export function groupEditorialStories(
  items: NewsItem[],
  detailMap: Record<number, NewsDetail | null>,
  options: GroupOptions = {},
): EditorialStoryGroup {
  const ranked = rankEditorialStories(items, detailMap);
  const supportingCount = options.supportingCount ?? 3;

  return {
    lead: ranked[0] ?? null,
    supporting: ranked.slice(1, supportingCount + 1),
    stream: ranked.slice(supportingCount + 1),
  };
}
