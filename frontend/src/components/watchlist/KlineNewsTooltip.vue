<script setup lang="ts">
import type { NewsEventMarker } from '../../types/api';

const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#ff5a72',
  negative: '#1fd39a',
  neutral: '#5fb8ff',
  mixed: '#8b7cff',
  unknown: '#8794a8',
};

defineProps<{
  event: NewsEventMarker;
  x: number;
  y: number;
  visible: boolean;
}>();
</script>

<template>
  <Transition name="tooltip-fade">
    <div
      v-if="visible && event.items.length"
      class="pointer-events-none fixed z-50 max-w-[280px] rounded-[12px] border border-border/70 bg-[rgba(10,17,27,0.95)] px-3 py-2 shadow-lg"
      :style="{ left: `${x}px`, top: `${y}px` }"
    >
      <div v-for="(item, i) in event.items.slice(0, 3)" :key="item.id" class="flex items-start gap-2 py-0.5" :class="i > 0 ? 'border-t border-border/30 mt-0.5' : ''">
        <span class="mt-[5px] h-[6px] w-[6px] shrink-0 rounded-full" :style="{ backgroundColor: SENTIMENT_COLORS[item.sentiment] ?? '#8794a8' }" />
        <span class="text-[11px] leading-[1.4] text-text/90">{{ item.title.length > 40 ? item.title.slice(0, 40) + '...' : item.title }}</span>
      </div>
      <div v-if="event.items.length > 3" class="mt-1 text-[10px] text-text-faint">+{{ event.items.length - 3 }} more</div>
    </div>
  </Transition>
</template>

<style scoped>
.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.15s ease;
}
.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
  opacity: 0;
}
</style>