import { computed, ref } from 'vue';

export function useVirtualList<T>(items: () => T[], itemHeight: number, overscan = 6) {
  const scrollTop = ref(0);
  const viewportHeight = ref(720);

  const totalHeight = computed(() => items().length * itemHeight);
  const startIndex = computed(() => Math.max(0, Math.floor(scrollTop.value / itemHeight) - overscan));
  const visibleCount = computed(() => Math.ceil(viewportHeight.value / itemHeight) + overscan * 2);
  const endIndex = computed(() => Math.min(items().length, startIndex.value + visibleCount.value));
  const visibleItems = computed(() =>
    items()
      .slice(startIndex.value, endIndex.value)
      .map((item, index) => ({
        item,
        index: startIndex.value + index,
      })),
  );

  const offsetY = computed(() => startIndex.value * itemHeight);

  function updateViewportHeight(height: number) {
    viewportHeight.value = height;
  }

  function updateScrollTop(top: number) {
    scrollTop.value = top;
  }

  return {
    totalHeight,
    visibleItems,
    offsetY,
    updateScrollTop,
    updateViewportHeight,
  };
}
