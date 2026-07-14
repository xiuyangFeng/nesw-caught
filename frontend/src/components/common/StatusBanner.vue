<script setup lang="ts">
const props = defineProps<{
  title: string;
  tone?: 'default' | 'warning' | 'danger' | 'success';
  detail?: string;
  kicker?: string;
}>();

function toneClasses(tone?: 'default' | 'warning' | 'danger' | 'success') {
  if (tone === 'warning') {
    return 'border-[color-mix(in_srgb,var(--warning)_32%,transparent)] bg-[var(--warning-soft)]';
  }
  if (tone === 'danger') {
    return 'border-[color-mix(in_srgb,var(--danger)_32%,transparent)] bg-[var(--danger-soft)]';
  }
  if (tone === 'success') {
    return 'border-[color-mix(in_srgb,var(--success)_32%,transparent)] bg-[var(--success-soft)]';
  }
  return 'border-border bg-panel-soft';
}

function kickerClasses(tone?: 'default' | 'warning' | 'danger' | 'success') {
  if (tone === 'warning') {
    return 'text-warning';
  }
  if (tone === 'danger') {
    return 'text-danger';
  }
  if (tone === 'success') {
    return 'text-success';
  }
  return 'text-muted';
}
</script>

<template>
  <section
    class="flex items-center justify-between gap-4 rounded-md border px-4 py-3"
    :class="toneClasses(props.tone)"
    :data-tone="props.tone ?? 'default'"
  >
    <div>
      <p v-if="kicker" class="label-mono mb-1" :class="kickerClasses(props.tone)" data-role="status-kicker">
        {{ kicker }}
      </p>
      <strong class="text-text">{{ title }}</strong>
      <p v-if="detail" class="mt-1 text-[13px] text-muted" data-role="status-detail">{{ detail }}</p>
    </div>
    <slot />
  </section>
</template>
