<script setup lang="ts">
import type { NewsItem } from '../../types/api';
import { sentimentText } from '../../utils/format';
import { formatMarketTime } from '../../utils/time';

const props = defineProps<{
  items: NewsItem[];
  highlightedEventTime: string | null;
}>();

defineEmits<{
  focusNews: [item: NewsItem];
}>();

// 后端 sentiment_label 为可空 string
function itemTone(sentiment: string | null | undefined) {
  if (sentiment === 'positive') return 'text-positive';
  if (sentiment === 'negative') return 'text-negative';
  return 'text-text-soft';
}

function itemDate(item: NewsItem) {
  return (item.published_at ?? item.fetched_at).slice(0, 10);
}
</script>

<template>
  <section
    class="grid gap-3 rounded-lg border border-border bg-panel p-4"
    data-role="trading-desk-news-feed"
  >
    <div class="flex items-center justify-between">
      <div>
        <p class="text-[11px] uppercase tracking-[0.24em] text-accent">Related News</p>
        <strong class="text-text">Event Timeline</strong>
      </div>
      <span class="text-[11px] uppercase tracking-[0.14em] text-text-faint">{{ items.length }} items</span>
    </div>

    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="grid gap-3 rounded-[16px] border p-3 text-left transition duration-150 ease-out hover:-translate-y-px"
      :class="
        highlightedEventTime && itemDate(item) === highlightedEventTime
          ? 'border-accent/60 bg-accent/10'
          : 'border-border/70 bg-panel-strong'
      "
      :data-highlighted="highlightedEventTime && itemDate(item) === highlightedEventTime ? 'true' : 'false'"
      :data-role="`trading-desk-news-item-${item.id}`"
      @click="$emit('focusNews', item)"
    >
      <div class="flex items-start justify-between gap-3">
        <div class="grid gap-1">
          <span class="text-[10px] uppercase tracking-[0.18em] text-text-faint">
            {{ itemDate(item) }} · {{ formatMarketTime(item.published_at ?? item.fetched_at, item.market) }}
          </span>
          <strong class="text-sm text-text">{{ item.title }}</strong>
        </div>
        <span class="text-[11px] uppercase tracking-[0.12em]" :class="itemTone(item.sentiment_label)">
          {{ sentimentText(item.sentiment_label) }}
        </span>
      </div>
      <p class="text-sm text-text-soft">{{ item.summary }}</p>
      <div class="flex items-center justify-between gap-2 text-[11px] uppercase tracking-[0.12em] text-text-faint">
        <span>{{ item.source_name }}</span>
        <span>{{ highlightedEventTime && itemDate(item) === highlightedEventTime ? 'Linked' : 'Timeline' }}</span>
      </div>
    </button>
  </section>
</template>
