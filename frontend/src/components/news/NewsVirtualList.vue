<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type { EditorialStoryEntry } from '../../utils/newsEditorial';
import { useVirtualList } from '../../composables/useVirtualList';
import NewsCard from './NewsCard.vue';

const props = defineProps<{
  entries: EditorialStoryEntry[];
}>();

const emit = defineEmits<{
  open: [id: number];
  'visible-ids': [ids: number[]];
}>();

const ROW_HEIGHT = 156;
const containerRef = ref<HTMLElement | null>(null);

const { totalHeight, visibleItems, offsetY, updateScrollTop, updateViewportHeight } = useVirtualList(
  () => props.entries,
  ROW_HEIGHT,
);

function syncViewport() {
  if (!containerRef.value) {
    return;
  }
  updateViewportHeight(containerRef.value.clientHeight);
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
</script>

<template>
  <div ref="containerRef" class="virtual-shell" @scroll="updateScrollTop(($event.target as HTMLElement).scrollTop)">
    <div :style="{ height: `${totalHeight}px` }" class="virtual-spacer">
      <div class="virtual-inner" :style="{ transform: `translateY(${offsetY}px)` }">
        <div
          v-for="vis in visibleItems"
          :key="vis.item.item.id"
          class="virtual-row"
          :style="{ height: `${ROW_HEIGHT}px` }"
        >
          <NewsCard :entry="vis.item" variant="stream-compact" @open="emit('open', $event)" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.virtual-shell {
  height: 100%;
  min-height: 680px;
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
