<script setup lang="ts">
import type { NewsDetail, NewsItem } from '../../types/api';
import { sentimentText } from '../../utils/format';
import { formatMarketTime, getMarketTimezoneLabel } from '../../utils/time';

defineProps<{
  item: NewsItem;
  detail?: NewsDetail | null;
  active?: boolean;
}>();

const emit = defineEmits<{
  select: [id: number];
}>();
</script>

<template>
  <article class="news-card" :data-active="Boolean(active)" @click="emit('select', item.id)">
    <div class="card-head">
      <span class="pill" :class="item.sentiment_label">{{ sentimentText(item.sentiment_label) }}</span>
      <span class="market-tag">{{ item.market.toUpperCase() }}</span>
      <span class="source">{{ item.source_name }}</span>
    </div>
    <h3>{{ item.title }}</h3>
    <p>{{ item.summary ?? '摘要待补充' }}</p>
    <div class="card-meta">
      <span>{{ formatMarketTime(item.published_at, item.market) }} {{ getMarketTimezoneLabel(item.market) }}</span>
      <span>{{ detail?.mentions.length ?? 0 }} 个关联股票</span>
      <span>{{ detail?.topic?.topic_title ?? '未归主题' }}</span>
    </div>
  </article>
</template>

<style scoped>
.news-card {
  height: 100%;
  border-radius: 20px;
  padding: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid transparent;
  transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}

.news-card[data-active='true'] {
  border-color: rgba(31, 94, 168, 0.28);
  box-shadow: 0 14px 30px rgba(31, 94, 168, 0.12);
}

.news-card:hover {
  transform: translateY(-2px);
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
  margin: 14px 0 10px;
  font-size: 17px;
}

p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
</style>
