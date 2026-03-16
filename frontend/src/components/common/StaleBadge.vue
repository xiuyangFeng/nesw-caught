<script setup lang="ts">
defineProps<{
  stale: boolean;
  label: string;
}>();
</script>

<template>
  <span class="stale-badge" :data-stale="stale">
    {{ stale ? `数据过期 · ${label}` : `已刷新 · ${label}` }}
  </span>
</template>

<style scoped>
.stale-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--positive);
  background: rgba(15, 123, 108, 0.1);
}

.stale-badge[data-stale='true'] {
  color: var(--warning);
  background: rgba(166, 111, 18, 0.14);
}
</style>
