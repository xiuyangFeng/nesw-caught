<script setup lang="ts">
import { computed } from 'vue';

import type { EditorialStoryEntry } from '../../utils/newsEditorial';
import { sentimentText } from '../../utils/format';
import { getNewsBody, getNewsSummary } from '../../utils/news';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../../utils/time';

const props = defineProps<{
  entry: EditorialStoryEntry;
}>();

const excerpt = computed(
  () => getNewsSummary(props.entry.detail ?? props.entry.item) ?? getNewsBody(props.entry.detail ?? { article: null, title: props.entry.item.title, summary: props.entry.item.summary }) ?? '该条新闻暂未生成更完整摘要。',
);

const emit = defineEmits<{
  open: [id: number];
}>();
</script>

<template>
  <article class="lead-story" @click="emit('open', entry.item.id)">
    <div class="lead-kicker">
      <span class="edition-tag">Lead Story</span>
      <span class="pill" :class="entry.item.sentiment_label">{{ sentimentText(entry.item.sentiment_label) }}</span>
      <span class="market-tag">{{ entry.item.market.toUpperCase() }}</span>
    </div>
    <h2>{{ entry.item.title }}</h2>
    <p class="lead-excerpt">{{ excerpt }}</p>
    <div class="lead-meta">
      <span>{{ entry.item.source_name }}</span>
      <span>{{ formatMarketTime(getNewsDisplayTimestamp(entry.item), entry.item.market) }} {{ getMarketTimezoneLabel(entry.item.market) }}</span>
      <span v-if="entry.detail?.topic">主题热度 {{ entry.detail.topic.importance_score.toFixed(2) }}</span>
      <span v-if="entry.detail?.mentions.length">{{ entry.detail.mentions.length }} 个关联股票</span>
    </div>
  </article>
</template>

<style scoped>
.lead-story {
  display: grid;
  gap: 14px;
  padding: 28px;
  border-radius: 24px;
  background:
    radial-gradient(circle at top right, rgba(255, 159, 47, 0.12), transparent 26%),
    linear-gradient(180deg, rgba(17, 25, 37, 0.98), rgba(10, 15, 24, 0.98));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 24px 60px rgba(2, 6, 12, 0.34);
  cursor: pointer;
}

.lead-kicker,
.lead-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 13px;
}

.edition-tag {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--accent);
}

h2 {
  margin: 0;
  max-width: 18ch;
  font-size: clamp(34px, 4vw, 52px);
  line-height: 1.12;
  letter-spacing: -0.04em;
}

.lead-excerpt {
  margin: 0;
  max-width: 72ch;
  color: var(--text-soft);
  font-size: 16px;
  line-height: 1.75;
}
</style>
