<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from 'vue';
import type { NewsEventMarker } from '../../types/api';

const SENTIMENT_COLORS: Record<string, string> = {
  positive: 'var(--positive)',
  negative: 'var(--negative)',
  neutral: 'var(--system)',
  mixed: 'var(--ai)',
  unknown: 'var(--text-faint)',
};

const SENTIMENT_LABELS: Record<string, string> = {
  positive: '正面',
  negative: '负面',
  neutral: '中性',
  mixed: '混合',
  unknown: '未知',
};

// 徽章底色 = 情绪色 13% 透明叠加（对应原 hex + '22' 后缀的视觉效果）。
function sentimentBadgeStyle(sentiment: string) {
  const color = SENTIMENT_COLORS[sentiment] ?? 'var(--text-faint)';
  return { backgroundColor: `color-mix(in srgb, ${color} 13%, transparent)`, color };
}

const props = defineProps<{
  event: NewsEventMarker;
  x: number;
  y: number;
  visible: boolean;
}>();

const emit = defineEmits<{
  close: [];
}>();

// window 不能在模板表达式里直接访问（会被编译成 _ctx.window 而在运行时报错），
// 所以在 script 里计算好弹层位置。
const popupStyle = computed(() => ({
  left: `${Math.min(props.x, window.innerWidth - 340)}px`,
  top: `${Math.min(props.y, window.innerHeight - 380)}px`,
}));

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
        class="fixed z-50 max-h-[360px] w-[320px] overflow-y-auto rounded-[14px] border border-border/70 bg-panel-stronger/95 px-3.5 py-3 shadow-xl"
        :style="popupStyle"
      >
        <header class="mb-2 flex items-center justify-between">
          <span class="num text-[11px] uppercase tracking-[0.16em] text-accent">{{ event.time }}</span>
          <button type="button" class="text-[11px] text-text-faint hover:text-text" @click="emit('close')">×</button>
        </header>
        <div class="grid gap-2.5">
          <article v-for="item in event.items" :key="item.id" class="grid gap-1 rounded-[10px] border border-border/40 bg-panel-soft px-2.5 py-2">
            <div class="flex items-start gap-2">
              <span
                class="mt-[3px] shrink-0 rounded-full px-1.5 py-[1px] text-[9px] font-medium uppercase"
                :style="sentimentBadgeStyle(item.sentiment)"
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