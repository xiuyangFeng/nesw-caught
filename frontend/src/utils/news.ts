import type { NewsDetail, NewsItem } from '../types/api';

function normalizeContent(value: string | null | undefined): string {
  return (value ?? '')
    .replace(/\s+/g, ' ')
    .replace(/[·•]/g, ' ')
    .trim()
    .toLowerCase();
}

export function getNewsSummary(item: Pick<NewsItem, 'title' | 'summary'>): string | null {
  const summary = item.summary?.trim();
  if (!summary) {
    return null;
  }

  return normalizeContent(summary) === normalizeContent(item.title) ? null : summary;
}

export function getNewsBody(detail: Pick<NewsDetail, 'title' | 'summary' | 'article'>): string | null {
  const content = detail.article?.content_text?.trim();
  if (!content) {
    return null;
  }

  const normalizedContent = normalizeContent(content);
  if (normalizedContent === normalizeContent(detail.title)) {
    return null;
  }
  if (normalizedContent === normalizeContent(detail.summary)) {
    return null;
  }
  return content;
}
