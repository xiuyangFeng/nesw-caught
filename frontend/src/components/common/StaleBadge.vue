<script setup lang="ts">
defineProps<{
  stale: boolean;
  label: string;
}>();
</script>

<template>
  <span
    class="inline-flex items-center rounded-full px-2.5 py-1.5 text-xs font-semibold"
    :class="stale ? 'bg-[#a66f1224] text-warning' : 'bg-[#0f7b6c1a] text-positive'"
    :data-stale="stale"
  >
    {{ stale ? `数据过期 · ${label}` : `已刷新 · ${label}` }}
  </span>
</template>
