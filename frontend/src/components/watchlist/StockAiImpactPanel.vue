<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';

import SectionCard from '../common/SectionCard.vue';
import { apiClient } from '../../api/client';
import type { StockImpact } from '../../types/api';
import { impactChipText, impactChipTone } from '../../utils/aiImpact';
import { formatMarketTime } from '../../utils/time';

const props = defineProps<{
  symbol: string;
}>();

const impacts = ref<StockImpact[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
let loadSeq = 0;

async function load(symbol: string) {
  const seq = ++loadSeq;
  loading.value = true;
  error.value = null;
  try {
    const response = await apiClient.getStockImpacts(symbol);
    if (seq === loadSeq) {
      impacts.value = response.data ?? [];
    }
  } catch (err) {
    if (seq === loadSeq) {
      impacts.value = [];
      error.value = err instanceof Error ? err.message : 'AI 影响加载失败';
    }
  } finally {
    if (seq === loadSeq) {
      loading.value = false;
    }
  }
}

onMounted(() => {
  void load(props.symbol);
});

watch(
  () => props.symbol,
  (next) => {
    void load(next);
  },
);
</script>

<template>
  <SectionCard eyebrow="AI Impact" title="AI 影响" subtitle="AI 精读新闻后对这只股票的利多/利空判断（含你的修正），新的在前">
    <div data-role="stock-ai-impacts">
      <p v-if="loading" class="text-sm text-muted">加载 AI 影响…</p>
      <p v-else-if="error" class="text-sm text-danger">{{ error }}</p>
      <p v-else-if="impacts.length === 0" class="text-sm text-muted" data-role="stock-ai-impacts-empty">暂无 AI 影响判断</p>
      <ol v-else class="grid gap-2">
        <li
          v-for="(impact, index) in impacts"
          :key="`${impact.news_id}-${index}`"
          class="grid gap-1 rounded-lg border border-border bg-panel-strong px-3.5 py-2.5"
          data-role="stock-ai-impact-row"
        >
          <div class="flex flex-wrap items-center gap-2 text-xs">
            <span
              class="rounded-full border px-2 py-0.5 font-semibold"
              :class="impactChipTone(impact.direction)"
              data-role="stock-ai-impact-chip"
            >
              {{ impactChipText(impact.direction, impact.strength) }}
            </span>
            <span
              v-if="impact.source === 'user'"
              class="rounded-full border border-accent/40 px-2 py-0.5 text-[11px] text-accent"
              data-role="stock-ai-impact-corrected"
            >
              已修正
            </span>
            <span class="ml-auto font-mono text-text-faint">{{ formatMarketTime(impact.published_at, 'cn') }}</span>
          </div>
          <RouterLink :to="`/news/${impact.news_id}`" class="text-sm font-semibold text-text hover:text-accent">
            {{ impact.title_zh || impact.news_title }}
          </RouterLink>
          <p v-if="impact.rationale" class="m-0 text-sm text-text-soft">{{ impact.rationale }}</p>
        </li>
      </ol>
    </div>
  </SectionCard>
</template>
