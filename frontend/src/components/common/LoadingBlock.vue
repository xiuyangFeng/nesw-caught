<script setup lang="ts">
defineProps<{
  loading: boolean;
  empty: boolean;
  loadingText?: string;
  emptyText?: string;
}>();
</script>

<template>
  <div v-if="loading || empty" class="loading-block">
    <span>{{ loading ? loadingText ?? '加载中...' : emptyText ?? '暂无数据' }}</span>
  </div>
  <slot v-else />
</template>

<style scoped>
.loading-block {
  display: grid;
  place-items: center;
  min-height: 120px;
  border-radius: 18px;
  border: 1px dashed var(--border-strong);
  color: var(--muted);
}
</style>
