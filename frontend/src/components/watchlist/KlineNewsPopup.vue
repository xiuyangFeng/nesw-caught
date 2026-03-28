<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue';
import type { NewsEventMarker } from '../../types/api';

const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#22c55e',
  negative: '#ef4444',
  neutral: '#3b82f6',
  mixed: '#a855f7',
  unknown: '#94a3b8',
};

const SENTIMENT_LABELS: Record<string, string> = {
  positive: '正面',
  negative: '负面',
  neutral: '中性',
  mixed: '混合',
  unknown: '未知',
};

const props = defineProps<{
  event: NewsEventMarker;
  x: number;
  y: number;
  visible: boolean;
}>();

const emit = defineEmits<{
  close: [];
}>();

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.visible) {
    emit('close');
  }
}

function handleBackdropClick(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (!target.closest('[data-role="kline-news-popup"]')) {
    emit('close');
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown));
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown));
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-40" @click="handleBackdropClick" />
    <Transition name="popup-fade">
      <div
        v-if="visible"
        data-role="kline-news-popup"
        class="fixed z-50 max-h-[360px] w-[320px] overflow-y-auto rounded-[14px] border border-border/70 bg-[rgba(7,12,22,0.96)] px-3.5 py-3 shadow-xl"
        :style="{ left: `${Math.min(x, window.innerWidth - 340)}px`, top: `${Math.min(y, window.innerHeight - 380)}px` }"
      >
        <header class="mb-2 flex items-center justify-between">
          <span class="text-[11px] uppercase tracking-[0.16em] text-[#ffb77d]">{{ event.time }}</span>
          <button type="button" class="text-[11px] text-text-faint hover:text-text" @click="emit('close')">×</button>
        </header>
        <div class="grid gap-2.5">
          <article v-for="item in event.items" :key="item.id" class="grid gap-1 rounded-[10px] border border-border/40 bg-[rgba(255,255,255,0.02)] px-2.5 py-2">
            <div class="flex items-start gap-2">
              <span
                class="mt-[3px] shrink-0 rounded-full px-1.5 py-[1px] text-[9px] font-medium uppercase"
                :style="{ backgroundColor: SENTIMENT_COLORS[item.sentiment] + '22', color: SENTIMENT_COLORS[item.sentiment] }"
              >
                {{ SENTIMENT_LABELS[item.sentiment] ?? item.sentiment }}
              </span>
              <span class="text-[12px] leading-[1.4] font-medium text-text">{{ item.title }}</span>
            </div>
            <p v-if="item.summary" class="line-clamp-3 text-[11px] leading-[1.4] text-text-faint">{{ item.summary }}</p>
          </article>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.popup-fade-enter-active,
.popup-fade-leave-active {
  transition: opacity 0.15s ease;
}
.popup-fade-enter-from,
.popup-fade-leave-to {
  opacity: 0;
}
</style>