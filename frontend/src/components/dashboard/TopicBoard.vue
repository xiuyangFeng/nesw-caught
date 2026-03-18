<script setup lang="ts">
import { useRouter } from 'vue-router';

import type { TopicItem } from '../../types/api';
import { formatMarketTime, getMarketTimezoneLabel } from '../../utils/time';
import { sentimentText } from '../../utils/format';

defineProps<{
  topics: TopicItem[];
}>();

const router = useRouter();

function openTopic(topicId: number) {
  router.push({ name: 'topic-detail', params: { id: topicId } });
}
</script>

<template>
  <div class="topic-board">
    <article v-for="topic in topics" :key="topic.id" class="topic-card terminal-surface" data-surface="terminal-card" role="button" tabindex="0" @click="openTopic(topic.id)" @keydown.enter="openTopic(topic.id)">
      <div class="topic-header">
        <span class="pill" :class="topic.sentiment_label">{{ sentimentText(topic.sentiment_label) }}</span>
        <strong>{{ topic.topic_title }}</strong>
      </div>
      <p>{{ topic.topic_summary ?? '主题摘要待补充' }}</p>
      <div class="topic-meta">
        <span>{{ topic.news_count }} 条新闻</span>
        <span>{{ topic.related_symbols.join(' · ') || '无关联股票' }}</span>
        <span>{{ formatMarketTime(topic.last_seen_at, topic.market) }} {{ getMarketTimezoneLabel(topic.market) }}</span>
      </div>
    </article>
  </div>
</template>

<style scoped>
.topic-board {
  display: grid;
  gap: 12px;
}

.topic-card {
  border-radius: 18px;
  padding: 16px;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
}

.topic-card:hover {
  border-color: rgba(125, 211, 252, 0.24);
  transform: translateY(-2px);
  box-shadow: 0 16px 30px rgba(4, 10, 18, 0.28);
}

.topic-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.topic-header strong {
  font-size: 16px;
}

p {
  margin: 12px 0;
  color: var(--text-soft);
}

.topic-meta {
  display: flex;
  gap: 12px;
  color: var(--text-faint);
  font-size: 12px;
  flex-wrap: wrap;
}
</style>
