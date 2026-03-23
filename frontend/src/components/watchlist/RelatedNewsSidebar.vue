<script setup lang="ts">
import type { NewsItem } from '../../types/api';

const props = defineProps<{
  items: NewsItem[];
  highlightedEventTime: string | null;
}>();

defineEmits<{
  focusNews: [item: NewsItem];
}>();

function itemTone(sentiment: string) {
  if (sentiment === 'positive') return 'text-positive';
  if (sentiment === 'negative') return 'text-negative';
  return 'text-text-soft';
}
</script>

<template>
  <section
    class="grid gap-3 rounded-[22px] border border-border bg-[linear-gradient(180deg,rgba(10,17,27,0.98),rgba(7,12,22,0.98))] p-4"
    data-role="related-news-sidebar"
  >
    <div class="flex items-center justify-between">
      <div>
        <p class="text-[11px] uppercase tracking-[0.24em] text-[#ffb77d]">Related News</p>
        <strong class="text-text">Story Flow</strong>
      </div>
      <span class="text-[11px] uppercase tracking-[0.14em] text-text-faint">{{ items.length }} items</span>
    </div>

    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="grid gap-2 rounded-[18px] border p-3 text-left transition duration-150 ease-out hover:-translate-y-px"
      :class="
        highlightedEventTime && (item.published_at ?? item.fetched_at).slice(0, 10) === highlightedEventTime
          ? 'border-[#ffb66d] bg-[rgba(255,159,47,0.08)]'
          : 'border-border/70 bg-black/10'
      "
      @click="$emit('focusNews', item)"
    >
      <div class="flex items-center justify-between gap-2">
        <strong class="text-sm text-text">{{ item.title }}</strong>
        <span class="text-[11px] uppercase tracking-[0.12em]" :class="itemTone(item.sentiment_label)">
          {{ item.sentiment_label }}
        </span>
      </div>
      <p class="text-sm text-text-soft">{{ item.summary }}</p>
      <span class="text-[11px] uppercase tracking-[0.12em] text-text-faint">{{ item.source_name }}</span>
    </button>
  </section>
</template>
