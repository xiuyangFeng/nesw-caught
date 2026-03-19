<script setup lang="ts">
defineProps<{
  metrics: Array<{
    label: string;
    value: string;
    note: string;
    tone: 'default' | 'positive' | 'negative';
  }>;
}>();

function metricToneClasses(tone: 'default' | 'positive' | 'negative') {
  if (tone === 'positive') {
    return 'text-positive';
  }
  if (tone === 'negative') {
    return 'text-negative';
  }
  return 'text-text';
}
</script>

<template>
  <section class="grid gap-3 md:grid-cols-2 xl:grid-cols-4" data-role="hero-grid">
    <article
      v-for="metric in metrics"
      :key="metric.label"
      class="surface rounded-[18px] p-[18px]"
      :data-role="'metric-card'"
      :data-tone="metric.tone"
    >
      <p class="m-0 text-[11px] uppercase tracking-[0.16em] text-muted" data-role="metric-label">
        {{ metric.label }}
      </p>
      <strong
        class="my-2 block text-[32px] tracking-[-0.04em]"
        :class="metricToneClasses(metric.tone)"
        data-role="metric-value"
      >
        {{ metric.value }}
      </strong>
      <span class="m-0 text-muted" data-role="metric-note">{{ metric.note }}</span>
    </article>
  </section>
</template>
