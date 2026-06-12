<script setup lang="ts">
const props = defineProps<{
  title: string;
  tone?: 'default' | 'warning' | 'danger' | 'success';
  detail?: string;
  kicker?: string;
}>();

function toneClasses(tone?: 'default' | 'warning' | 'danger' | 'success') {
  if (tone === 'warning') {
    return 'border-system/20 bg-[linear-gradient(180deg,rgba(15,27,40,0.96),rgba(11,20,31,0.96))]';
  }
  if (tone === 'danger') {
    return 'border-danger/30 bg-[linear-gradient(180deg,rgba(31,17,24,0.92),rgba(18,11,17,0.94))]';
  }
  if (tone === 'success') {
    return 'border-success/25 bg-[linear-gradient(180deg,rgba(11,28,22,0.92),rgba(10,18,15,0.94))]';
  }
  return 'border-border bg-panel-soft';
}
</script>

<template>
  <section
    class="flex items-center justify-between gap-4 rounded-2xl border px-[18px] py-[14px]"
    :class="toneClasses(props.tone)"
    :data-tone="props.tone ?? 'default'"
  >
    <div>
      <p v-if="kicker" class="mb-1 text-[10px] uppercase tracking-[0.16em] text-system" data-role="status-kicker">
        {{ kicker }}
      </p>
      <strong class="text-text">{{ title }}</strong>
      <p v-if="detail" class="mt-1 text-[13px] text-muted" data-role="status-detail">{{ detail }}</p>
    </div>
    <slot />
  </section>
</template>
