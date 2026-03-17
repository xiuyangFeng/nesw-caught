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
  gap: 16px;
  padding: 32px;
  border-radius: 32px;
  background:
    radial-gradient(circle at top right, rgba(199, 161, 89, 0.12), transparent 28%),
    rgba(255, 252, 247, 0.96);
  border: 1px solid rgba(93, 67, 28, 0.12);
  box-shadow: 0 24px 60px rgba(88, 64, 30, 0.12);
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
  letter-spacing: 0.14em;
  color: var(--neutral);
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
  color: #50483f;
  font-size: 16px;
  line-height: 1.8;
}
</style>
