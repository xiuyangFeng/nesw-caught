<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type { EditorialStoryEntry } from '../../utils/newsEditorial';
import { useVirtualList } from '../../composables/useVirtualList';
import NewsCard from './NewsCard.vue';

const props = defineProps<{
  entries: EditorialStoryEntry[];
  selectedId?: number | null;
  readIds?: ReadonlySet<number>;
}>();

const emit = defineEmits<{
  open: [id: number];
  'visible-ids': [ids: number[]];
}>();

const ROW_HEIGHT = 156;
/** Explicit scroll-root height so clientHeight stays usable (avoid collapsing height:100%). */
const SCROLL_ROOT_HEIGHT = 'min(720px, calc(100vh - 220px))';
const FALLBACK_VIEWPORT_HEIGHT = 680;
const containerRef = ref<HTMLElement | null>(null);

const { totalHeight, visibleItems, offsetY, updateScrollTop, updateViewportHeight } = useVirtualList(
  () => props.entries,
  ROW_HEIGHT,
);

function syncViewport() {
  if (!containerRef.value) {
    return;
  }
  const measured = containerRef.value.clientHeight;
  updateViewportHeight(measured > 0 ? measured : FALLBACK_VIEWPORT_HEIGHT);
}

onMounted(async () => {
  await nextTick();
  syncViewport();
  window.addEventListener('resize', syncViewport);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncViewport);
});

watch(
  visibleItems,
  (items) => {
    emit('visible-ids', items.map((item) => item.item.item.id));
  },
  { immediate: true },
);

function scrollToIndex(index: number): void {
  if (!containerRef.value) {
    return;
  }
  containerRef.value.scrollTop = Math.max(0, index * ROW_HEIGHT - containerRef.value.clientHeight / 2);
}

defineExpose({ scrollToIndex });
</script>

<template>
  <div
    ref="containerRef"
    class="virtual-shell"
    data-role="news-virtual-scroll-root"
    :style="{ height: SCROLL_ROOT_HEIGHT }"
    @scroll="updateScrollTop(($event.target as HTMLElement).scrollTop)"
  >
    <div :style="{ height: `${totalHeight}px` }" class="virtual-spacer">
      <div class="virtual-inner" :style="{ transform: `translateY(${offsetY}px)` }">
        <div
          v-for="vis in visibleItems"
          :key="vis.item.item.id"
          class="virtual-row"
          :style="{ height: `${ROW_HEIGHT}px` }"
        >
          <NewsCard
            :entry="vis.item"
            variant="stream-compact"
            :selected="vis.item.item.id === selectedId"
            :read="readIds?.has(vis.item.item.id) ?? false"
            @open="emit('open', $event)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.virtual-shell {
  /* Height comes from inline SCROLL_ROOT_HEIGHT (fixed/viewport), not collapsing 100%. */
  min-height: 480px;
  overflow: auto;
}

.virtual-spacer {
  position: relative;
}

.virtual-inner {
  position: absolute;
  inset: 0 0 auto;
}

.virtual-row {
  padding-bottom: 12px;
}
</style>
