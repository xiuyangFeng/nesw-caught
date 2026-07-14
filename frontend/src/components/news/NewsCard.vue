<script setup lang="ts">
import { computed } from 'vue';

import type { EditorialStoryEntry } from '../../utils/newsEditorial';
import { sentimentText } from '../../utils/format';
import { getNewsSummary } from '../../utils/news';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../../utils/time';

const props = withDefaults(
  defineProps<{
    entry: EditorialStoryEntry;
    variant?: 'supporting' | 'stream' | 'stream-compact';
  }>(),
  {
    variant: 'stream',
  },
);

const summary = computed(() => getNewsSummary(props.entry.detail ?? props.entry.item) ?? '摘要待补充');
const publishedLabel = computed(
  () => `${formatMarketTime(getNewsDisplayTimestamp(props.entry.item), props.entry.item.market)} ${getMarketTimezoneLabel(props.entry.item.market)}`,
);
const topicLabel = computed(() => props.entry.detail?.topic?.topic_title ?? '未归主题');

const emit = defineEmits<{
  open: [id: number];
}>();
</script>

<template>
  <article class="news-card" :class="`news-card--${variant}`" data-role="news-card-shell" @click="emit('open', entry.item.id)">
    <div class="card-head" data-role="news-card-head">
      <span class="pill" :class="entry.item.sentiment_label">{{ sentimentText(entry.item.sentiment_label) }}</span>
      <span class="market-tag">{{ entry.item.market.toUpperCase() }}</span>
      <span class="source">{{ entry.item.source_name }}</span>
    </div>
    <div class="news-card__body" :class="{ 'news-card__supporting-body': variant === 'supporting', 'news-card__compact-body': variant === 'stream-compact' }">
      <div class="news-card__copy" :class="{ 'news-card__supporting-copy': variant === 'supporting', 'news-card__compact-copy': variant === 'stream-compact' }">
        <h3 data-role="news-card-title">{{ entry.item.title }}</h3>
        <p class="summary">{{ summary }}</p>
      </div>
      <div class="news-card__meta" :class="{ 'news-card__supporting-meta': variant === 'supporting', 'news-card__compact-meta': variant === 'stream-compact' }">
        <span class="news-card__time">{{ publishedLabel }}</span>
        <span>{{ topicLabel }}</span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.news-card {
  display: grid;
  gap: 10px;
  border-radius: var(--r-md);
  padding: 14px 16px;
  background: var(--panel);
  border: 1px solid var(--border);
  transition: border-color 160ms ease, background-color 160ms ease;
  cursor: pointer;
}

.news-card:hover {
  border-color: var(--border-strong);
  background: var(--panel-strong);
}

.news-card--stream-compact {
  height: 144px;
  padding: 12px 14px;
  gap: 8px;
  overflow: hidden;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 11px;
}

.market-tag {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.source {
  color: var(--muted);
}

h3 {
  margin: 0;
  font-size: 16px;
  line-height: 1.4;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text);
}

.news-card__body {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(168px, 0.5fr);
  gap: 18px;
  align-items: start;
}

.news-card__copy {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.news-card__meta {
  display: grid;
  gap: 8px;
  align-content: start;
  justify-items: start;
  padding-left: 14px;
  border-left: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
  line-height: 1.55;
}

.news-card__meta span {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  -webkit-line-clamp: 2;
}

.news-card__time {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
  color: var(--text-faint);
}

.news-card__compact-body {
  grid-template-columns: minmax(0, 1.7fr) minmax(132px, 0.48fr);
  gap: 14px;
}

.news-card__compact-copy {
  gap: 6px;
}

.news-card--stream-compact h3 {
  font-size: 15px;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  -webkit-line-clamp: 2;
}

.news-card__compact-meta {
  gap: 6px;
  padding-left: 12px;
  font-size: 11px;
}

.summary {
  margin: 0;
  color: var(--text-soft);
  font-size: 14px;
  line-height: 1.65;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  -webkit-line-clamp: 2;
}

.news-card--stream-compact .summary {
  font-size: 13px;
  line-height: 1.45;
}

@media (max-width: 860px) {
  .news-card__body {
    grid-template-columns: 1fr;
  }

  .news-card__meta {
    padding-left: 0;
    border-left: none;
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }

  .news-card__compact-body {
    grid-template-columns: minmax(0, 1.65fr) minmax(108px, 0.5fr);
  }

  .news-card--stream-compact .news-card__meta {
    padding-top: 0;
    border-top: none;
  }
}
</style>
