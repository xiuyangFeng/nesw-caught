<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

import LoadingBlock from '../common/LoadingBlock.vue';
import SectionCard from '../common/SectionCard.vue';
import type { NewsItem } from '../../types/api';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../../utils/time';

const props = defineProps<{
  items: NewsItem[];
  loading: boolean;
}>();

defineEmits<{
  (event: 'selectNews', id: number): void;
}>();

// 首页只展示前 8 条,完整列表走 News Feed 页面
const visibleItems = computed(() => props.items.slice(0, 8));

function getTimestampLabel(item: NewsItem) {
  const timestamp = getNewsDisplayTimestamp(item);
  return `${formatMarketTime(timestamp, item.market)} ${getMarketTimezoneLabel(item.market)}`;
}
</script>

<template>
  <SectionCard
    class="h-full"
    eyebrow="News Wire"
    title="News Feed"
    subtitle="新闻主列，保持紧凑扫描密度"
    data-role="dashboard-column-feed"
  >
    <LoadingBlock :loading="loading" :empty="items.length === 0" :skeletonType="'news'" :skeletonCount="3">
      <div class="grid gap-3">
        <div class="dashboard-column-scroller" data-role="dashboard-column-scroller">
          <button
            v-for="item in visibleItems"
            :key="item.id"
            class="dashboard-feed-item"
            :class="{
              'dashboard-feed-item--breaking': (item as any).editorial_score >= 8.5,
              'positive': item.sentiment_label === 'positive',
              'negative': item.sentiment_label === 'negative'
            }"
            data-role="dashboard-feed-item"
            type="button"
            @click="$emit('selectNews', item.id)"
          >
            <div class="flex flex-wrap items-center gap-2 text-[11px] text-muted">
              <span
                v-if="(item as any).editorial_score >= 8.5"
                class="inline-flex h-2 w-2 rounded-full shrink-0 animate-pulse pulse-dot"
                :class="item.sentiment_label === 'positive' ? 'bg-positive' : 'bg-negative'"
                :style="{ '--pulse-color': item.sentiment_label === 'positive' ? 'color-mix(in srgb, var(--positive) 35%, transparent)' : 'color-mix(in srgb, var(--negative) 35%, transparent)' }"
              />
              <span class="pill" :class="item.sentiment_label">{{ item.sentiment_label }}</span>
              <span>{{ item.source_name }}</span>
              <span>{{ getTimestampLabel(item) }}</span>
            </div>
            <strong class="block text-[14px] leading-5 text-text">{{ item.title }}</strong>
            <p class="m-0 line-clamp-1 text-[12px] leading-5 text-muted">{{ item.summary }}</p>
          </button>
        </div>

        <RouterLink
          class="inline-flex min-h-10 items-center justify-center rounded-full border border-border bg-white/[0.04] text-[13px] font-semibold text-text transition duration-150 ease-out hover:-translate-y-px hover:border-system/25 hover:bg-white/[0.06]"
          to="/news"
        >
          打开完整 News Feed
        </RouterLink>
      </div>
    </LoadingBlock>
  </SectionCard>
</template>

<style scoped>
.dashboard-column-scroller {
  display: grid;
  gap: 10px;
}

@media (min-width: 1280px) {
  .dashboard-column-scroller {
    max-height: clamp(28rem, calc(100vh - 21rem), 40rem);
    overflow-y: auto;
    padding-right: 4px;
  }
}

.dashboard-feed-item {
  display: grid;
  gap: 6px;
  width: 100%;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--panel-soft);
  padding: 12px 12px;
  text-align: left;
  cursor: pointer;
  transition: transform 150ms ease, border-color 150ms ease, background 150ms ease;
}

.dashboard-feed-item:hover {
  transform: translateY(-1px);
  border-color: rgba(58, 210, 230, 0.35);
  background: var(--panel-strong);
}

.dashboard-feed-item:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.dashboard-feed-item--breaking {
  position: relative;
  border-left-width: 4px;
  border-left-style: solid;
  border-left-color: var(--accent);
}

.dashboard-feed-item--breaking.positive {
  border-left-color: var(--positive);
  background: var(--positive-soft);
}

.dashboard-feed-item--breaking.negative {
  border-left-color: var(--negative);
  background: var(--negative-soft);
}

.dashboard-feed-item--breaking:hover {
  transform: translateY(-1px);
}

.dashboard-feed-item--breaking.positive:hover {
  border-color: var(--positive);
  background: var(--positive-soft);
}

.dashboard-feed-item--breaking.negative:hover {
  border-color: var(--negative);
  background: var(--negative-soft);
}
</style>
