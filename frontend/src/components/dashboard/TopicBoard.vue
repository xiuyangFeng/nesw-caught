<script setup lang="ts">
import { useRouter } from 'vue-router';

import type { TopicItem } from '../../types/api';
import { sentimentText } from '../../utils/format';
import { formatMarketTime, getMarketTimezoneLabel } from '../../utils/time';

defineProps<{
  topics: TopicItem[];
}>();

const router = useRouter();

function openTopic(topicId: number) {
  router.push({ name: 'topic-detail', params: { id: topicId } });
}
</script>

<template>
  <div class="grid gap-3">
    <article
      v-for="topic in topics"
      :key="topic.id"
      class="terminal-surface cursor-pointer rounded-lg border border-border p-4 transition duration-150 ease-out hover:-translate-y-0.5 hover:border-accent/40"
      data-surface="terminal-card"
      role="button"
      tabindex="0"
      @click="openTopic(topic.id)"
      @keydown.enter="openTopic(topic.id)"
    >
      <div class="flex items-center justify-between gap-3" data-role="topic-card-head">
        <div class="flex min-w-0 items-center gap-2.5">
          <span class="pill" :class="topic.sentiment_label">{{ sentimentText(topic.sentiment_label) }}</span>
          <strong class="truncate text-base text-text">{{ topic.display_name?.trim() || topic.topic_title }}</strong>
        </div>
        <span class="shrink-0 text-[10px] uppercase tracking-[0.18em] text-muted font-mono">Signal</span>
      </div>
      <p class="my-3 text-text-soft">{{ topic.topic_summary ?? '主题摘要待补充' }}</p>
      <div class="flex flex-wrap gap-3 text-xs text-text-faint font-mono tabular-nums" data-role="topic-meta">
        <span>{{ topic.news_count }} 条新闻</span>
        <span>{{ topic.related_symbols.join(' · ') || '无关联股票' }}</span>
        <span>{{ formatMarketTime(topic.last_seen_at, topic.market) }} {{ getMarketTimezoneLabel(topic.market) }}</span>
      </div>
    </article>
  </div>
</template>
