<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';

import type { NewsDetail, NewsItem } from '../../types/api';
import { useVirtualList } from '../../composables/useVirtualList';
import NewsCard from './NewsCard.vue';

const props = defineProps<{
  items: NewsItem[];
  detailMap: Record<number, NewsDetail | null>;
  activeId: number | null;
}>();

const emit = defineEmits<{
  select: [id: number];
}>();

const containerRef = ref<HTMLElement | null>(null);
const virtualItems = computed(() => props.items);
const { totalHeight, visibleItems, offsetY, updateScrollTop, updateViewportHeight } = useVirtualList(
  () => virtualItems.value,
  184,
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
</script>

<template>
  <div ref="containerRef" class="virtual-shell" @scroll="updateScrollTop(($event.target as HTMLElement).scrollTop)">
    <div :style="{ height: `${totalHeight}px` }" class="virtual-spacer">
      <div class="virtual-inner" :style="{ transform: `translateY(${offsetY}px)` }">
        <div
          v-for="entry in visibleItems"
          :key="entry.item.id"
          class="virtual-row"
        >
          <NewsCard
            :item="entry.item"
            :detail="detailMap[entry.item.id]"
            :active="activeId === entry.item.id"
            @select="emit('select', $event)"
          />
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
  height: 184px;
  padding-bottom: 12px;
}
</style>
