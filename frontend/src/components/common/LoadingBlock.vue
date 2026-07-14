<script setup lang="ts">
import SkeletonFeed from './SkeletonFeed.vue';

withDefaults(
  defineProps<{
    loading: boolean;
    empty: boolean;
    loadingText?: string;
    emptyText?: string;
    skeletonType?: 'news' | 'dashboard' | 'watchlist' | 'detail';
    skeletonCount?: number;
  }>(),
  {
    skeletonType: 'news',
    skeletonCount: 3,
  }
);
</script>

<template>
  <div class="transition-container">
    <transition name="fade-cross" mode="out-in"><div v-if="loading && empty" :key="'skeleton'" class="w-full"><SkeletonFeed :type="skeletonType" :count="skeletonCount" /></div><div v-else-if="empty" :key="'empty'" class="grid min-h-[140px] place-items-center rounded-lg border border-dashed border-border text-muted bg-panel-soft p-6 text-center w-full"><div class="flex flex-col items-center gap-2"><span class="text-2xl">📦</span><span class="text-sm tracking-wide">{{ emptyText ?? '暂无数据' }}</span></div></div><div v-else :key="'content'" class="w-full"><slot /></div></transition>
  </div>
</template>

<style scoped>
.transition-container {
  width: 100%;
  position: relative;
}

/* 局部交叉渐变动画 */
.fade-cross-enter-active,
.fade-cross-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.fade-cross-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.fade-cross-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
