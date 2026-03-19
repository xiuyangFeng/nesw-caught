<script setup lang="ts">
defineProps<{
  loading: boolean;
  empty: boolean;
  loadingText?: string;
  emptyText?: string;
}>();
</script>

<template>
  <div
    v-if="loading || empty"
    class="grid min-h-[120px] place-items-center rounded-[18px] border border-dashed border-border-strong text-muted"
  >
    <span>{{ loading ? loadingText ?? '加载中...' : emptyText ?? '暂无数据' }}</span>
  </div>
  <slot v-else />
</template>
