<script setup lang="ts">
import { computed, ref } from 'vue';

import type { TokenDailyStats } from './types';

const props = defineProps<{
  daily: TokenDailyStats[];
}>();

const hoveredIdx = ref<number | null>(null);
const dailyData = computed(() => props.daily ?? []);
const maxTotal = computed(() => Math.max(...dailyData.value.map((item) => item.total_tokens), 0));

const bars = computed(() => dailyData.value.map((item) => {
  const total = Math.max(item.total_tokens, 0);
  const heightPct = maxTotal.value > 0 ? Math.max(6, (total / maxTotal.value) * 100) : 6;
  const promptPct = total > 0 ? Math.max(0, Math.min(100, (item.prompt_tokens / total) * 100)) : 50;
  return {
    ...item,
    heightPct,
    promptPct,
    completionPct: 100 - promptPct,
  };
}));

const activeDay = computed(() => (
  hoveredIdx.value === null ? null : bars.value[hoveredIdx.value] ?? null
));

function compactNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(value >= 10_000 ? 0 : 1)}K`;
  return value.toLocaleString();
}
</script>

<template>
  <section class="grid min-h-[260px] gap-4 rounded-[20px] border border-border/70 bg-black/10 p-4" data-role="token-trend-card">
    <header class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p class="label-mono text-[10px] text-accent">TOKEN FLOW / 7D</p>
        <h3 class="mt-1 text-sm font-bold text-text">输入与输出流量</h3>
      </div>
      <div class="flex items-center gap-3 font-mono text-[10px] text-text-faint">
        <span class="inline-flex items-center gap-1.5"><i class="h-2 w-2 rounded-sm bg-accent" />输入</span>
        <span class="inline-flex items-center gap-1.5"><i class="h-2 w-2 rounded-sm bg-ai" />输出</span>
      </div>
    </header>

    <div v-if="bars.length > 0" class="grid gap-3" data-role="chart-container">
      <div class="relative h-44 overflow-hidden rounded-[16px] border border-border/50 bg-[linear-gradient(180deg,color-mix(in_srgb,var(--panel-strong)_72%,transparent),transparent)] px-3 pt-5">
        <div class="pointer-events-none absolute inset-x-3 top-5 grid h-[118px] content-between">
          <span v-for="line in 4" :key="line" class="block border-t border-dashed border-border/45" />
        </div>

        <div
          class="relative z-10 grid h-[138px] items-end gap-2"
          :style="{ gridTemplateColumns: `repeat(${bars.length}, minmax(34px, 1fr))` }"
        >
          <button
            v-for="(bar, index) in bars"
            :key="bar.date"
            type="button"
            class="group grid h-full min-w-0 grid-rows-[1fr_auto] items-end gap-2 rounded-lg outline-none"
            data-role="token-day-bar"
            @mouseenter="hoveredIdx = index"
            @mouseleave="hoveredIdx = null"
            @focus="hoveredIdx = index"
            @blur="hoveredIdx = null"
          >
            <div class="flex h-full flex-col items-center justify-end">
              <span class="mb-1 font-mono text-[9px] tabular-nums text-text-faint transition group-hover:text-text">
                {{ compactNumber(bar.total_tokens) }}
              </span>
              <span
                class="flex w-full max-w-14 flex-col-reverse overflow-hidden rounded-t-md border border-border/60 bg-panel shadow-[0_0_16px_color-mix(in_srgb,var(--accent)_8%,transparent)] transition duration-200 group-hover:-translate-y-1 group-hover:border-accent/50"
                :style="{ height: `${bar.heightPct}%` }"
              >
                <i
                  class="block w-full bg-accent/85"
                  data-role="prompt-token-segment"
                  :style="{ height: `${bar.promptPct}%` }"
                />
                <i
                  class="block w-full bg-ai/80"
                  data-role="completion-token-segment"
                  :style="{ height: `${bar.completionPct}%` }"
                />
              </span>
            </div>
            <span class="truncate font-mono text-[9px] text-text-faint">{{ bar.date.slice(5) }}</span>
          </button>
        </div>
      </div>

      <div class="min-h-11 rounded-[14px] border border-border/60 bg-panel/65 px-3 py-2 font-mono text-[10px] text-text-faint">
        <div v-if="activeDay" class="flex flex-wrap items-center justify-between gap-2">
          <strong class="text-text">{{ activeDay.date }}</strong>
          <span>合计 <b class="text-text">{{ activeDay.total_tokens.toLocaleString() }}</b></span>
          <span>输入 {{ activeDay.prompt_tokens.toLocaleString() }}</span>
          <span>输出 {{ activeDay.completion_tokens.toLocaleString() }}</span>
        </div>
        <p v-else class="m-0">悬停或聚焦某一天，查看 Token 构成。</p>
      </div>
    </div>

    <div v-else class="grid min-h-40 place-items-center rounded-[16px] border border-dashed border-border/60 bg-black/10 text-center">
      <div>
        <p class="label-mono text-[10px] text-text-faint">NO TOKEN LEDGER</p>
        <p class="mt-2 text-sm text-text-soft">暂无足够历史 Token 用量趋势数据</p>
      </div>
    </div>
  </section>
</template>
