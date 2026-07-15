<script setup lang="ts">
import type { Market } from '../../types/api';

defineProps<{
  markets: Array<{ label: string; value: Market | null }>;
  sentiments: Array<{ label: string; value: string | null }>;
  selectedMarket: Market | null;
  selectedSentiment: string | null;
}>();

const emit = defineEmits<{
  (event: 'update:selectedMarket', value: Market | null): void;
  (event: 'update:selectedSentiment', value: string | null): void;
}>();
</script>

<template>
  <div
    class="surface rounded-[14px] border border-border/80 bg-panel-soft/60 px-4 py-3 flex flex-wrap items-center justify-between gap-3 shrink-0"
    data-role="dashboard-filter-bar"
  >
    <div class="flex items-center gap-1.5">
      <span class="text-[11px] text-muted uppercase tracking-wider font-semibold mr-1.5">市场范围</span>
      <button
        v-for="m in markets"
        :key="m.value ?? 'all'"
        class="text-[11px] font-semibold px-3 py-1.5 rounded-full border transition duration-150"
        :class="selectedMarket === m.value ? 'bg-accent/10 border-accent/40 text-accent font-bold' : 'bg-white/[0.02] border-border/60 text-muted hover:text-text hover:bg-white/[0.04]'"
        type="button"
        @click="emit('update:selectedMarket', m.value)"
      >
        {{ m.label }}
      </button>
    </div>

    <div class="flex items-center gap-1.5">
      <span class="text-[11px] text-muted uppercase tracking-wider font-semibold mr-1.5">舆情过滤</span>
      <button
        v-for="s in sentiments"
        :key="s.value ?? 'all'"
        class="text-[11px] font-semibold px-3 py-1.5 rounded-full border transition duration-150"
        :class="selectedSentiment === s.value ? 'bg-accent/10 border-accent/40 text-accent font-bold' : 'bg-white/[0.02] border-border/60 text-muted hover:text-text hover:bg-white/[0.04]'"
        type="button"
        @click="emit('update:selectedSentiment', s.value)"
      >
        {{ s.label }}
      </button>
    </div>
  </div>
</template>
