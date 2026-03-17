<script setup lang="ts">
import { computed } from 'vue';

import type { EditorialStoryEntry } from '../../utils/newsEditorial';
import { sentimentText } from '../../utils/format';
import { getNewsSummary } from '../../utils/news';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../../utils/time';

const props = withDefaults(
  defineProps<{
    entry: EditorialStoryEntry;
    variant?: 'supporting' | 'stream';
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
  <article class="news-card" :class="`news-card--${variant}`" @click="emit('open', entry.item.id)">
    <div class="card-head">
      <span class="pill" :class="entry.item.sentiment_label">{{ sentimentText(entry.item.sentiment_label) }}</span>
      <span class="market-tag">{{ entry.item.market.toUpperCase() }}</span>
      <span class="source">{{ entry.item.source_name }}</span>
    </div>

    <template v-if="variant === 'supporting'">
      <div class="news-card__supporting-body">
        <div class="news-card__supporting-copy">
          <h3>{{ entry.item.title }}</h3>
          <p class="summary">{{ summary }}</p>
        </div>
        <div class="news-card__supporting-meta">
          <span>{{ publishedLabel }}</span>
          <span>{{ topicLabel }}</span>
        </div>
      </div>
    </template>

    <template v-else>
      <h3>{{ entry.item.title }}</h3>
      <p class="summary">{{ summary }}</p>
      <div class="card-meta">
        <span>{{ publishedLabel }}</span>
        <span>{{ topicLabel }}</span>
      </div>
    </template>
  </article>
</template>

<style scoped>
.news-card {
  display: grid;
  gap: 12px;
  border-radius: 18px;
  padding: 18px 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
  cursor: pointer;
}

.news-card:hover {
  transform: translateY(-2px);
  border-color: rgba(102, 184, 255, 0.24);
  box-shadow: 0 16px 36px rgba(2, 6, 12, 0.28);
}

.news-card--supporting {
  gap: 14px;
  min-height: 0;
}

.card-head,
.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 12px;
}

h3 {
  margin: 0;
  font-size: 22px;
  line-height: 1.28;
  letter-spacing: -0.02em;
}

.news-card--stream h3 {
  font-size: 21px;
}

.news-card__supporting-body {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(138px, 0.55fr);
  gap: 16px;
  align-items: start;
}

.news-card__supporting-copy {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.news-card__supporting-meta {
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

.news-card__supporting-meta span {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  -webkit-line-clamp: 2;
}

.summary {
  margin: 0;
  color: var(--text-soft);
  font-size: 14px;
  line-height: 1.65;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-card--supporting .summary {
  -webkit-line-clamp: 2;
}

.news-card--stream .summary {
  -webkit-line-clamp: 4;
}

@media (max-width: 860px) {
  .news-card__supporting-body {
    grid-template-columns: 1fr;
  }

  .news-card__supporting-meta {
    padding-left: 0;
    border-left: none;
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }
}
</style>
