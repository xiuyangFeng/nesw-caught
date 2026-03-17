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
    <h3>{{ entry.item.title }}</h3>
    <p class="summary">{{ summary }}</p>
    <div class="card-meta">
      <span>{{ formatMarketTime(getNewsDisplayTimestamp(entry.item), entry.item.market) }} {{ getMarketTimezoneLabel(entry.item.market) }}</span>
      <span v-if="entry.detail?.topic">{{ entry.detail.topic.topic_title }}</span>
      <span v-else>未归主题</span>
    </div>
  </article>
</template>

<style scoped>
.news-card {
  display: grid;
  gap: 12px;
  border-radius: 24px;
  padding: 20px 22px;
  background: rgba(255, 252, 247, 0.9);
  border: 1px solid var(--border);
  transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
  cursor: pointer;
}

.news-card:hover {
  transform: translateY(-2px);
  border-color: rgba(31, 94, 168, 0.18);
  box-shadow: 0 16px 36px rgba(76, 57, 28, 0.08);
}

.news-card--supporting {
  min-height: 172px;
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
  font-size: 23px;
  line-height: 1.28;
  letter-spacing: -0.02em;
}

.news-card--stream h3 {
  font-size: 21px;
}

.summary {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.7;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-card--supporting .summary {
  -webkit-line-clamp: 3;
}

.news-card--stream .summary {
  -webkit-line-clamp: 4;
}
</style>
