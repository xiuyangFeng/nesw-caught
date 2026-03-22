<script setup lang="ts">
import { RouterLink } from 'vue-router';

defineProps<{
  metrics: Array<{
    label: string;
    value: string;
    note: string;
    tone: 'default' | 'positive' | 'negative';
    to?: string;
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
    <template v-for="metric in metrics" :key="metric.label">
      <RouterLink
        v-if="metric.to"
        :to="metric.to"
        class="surface block rounded-[14px] border border-border/90 bg-[linear-gradient(180deg,rgba(11,18,28,0.98),rgba(8,14,23,0.98))] p-[16px] transition duration-150 ease-out hover:-translate-y-px hover:border-[#ff9f2f66] hover:bg-[linear-gradient(180deg,rgba(15,24,36,0.98),rgba(9,16,25,0.98))]"
        data-role="metric-link"
        :data-tone="metric.tone"
      >
        <div data-role="metric-shell">
        <p class="m-0 text-[11px] uppercase tracking-[0.16em] text-muted" data-role="metric-label">
          {{ metric.label }}
        </p>
        <strong
          class="mb-1.5 mt-2 block text-[32px] tracking-[-0.05em] font-semibold"
          :class="metricToneClasses(metric.tone)"
          data-role="metric-value"
        >
          {{ metric.value }}
        </strong>
        <span class="m-0 text-[11px] uppercase tracking-[0.12em] text-muted" data-role="metric-note">{{ metric.note }}</span>
        </div>
      </RouterLink>

      <article
        v-else
        class="surface rounded-[14px] border border-border/90 bg-[linear-gradient(180deg,rgba(11,18,28,0.98),rgba(8,14,23,0.98))] p-[16px]"
        :data-role="'metric-card'"
        :data-tone="metric.tone"
      >
        <div data-role="metric-shell">
        <p class="m-0 text-[11px] uppercase tracking-[0.16em] text-muted" data-role="metric-label">
          {{ metric.label }}
        </p>
        <strong
          class="mb-1.5 mt-2 block text-[32px] tracking-[-0.05em] font-semibold"
          :class="metricToneClasses(metric.tone)"
          data-role="metric-value"
        >
          {{ metric.value }}
        </strong>
        <span class="m-0 text-[11px] uppercase tracking-[0.12em] text-muted" data-role="metric-note">{{ metric.note }}</span>
        </div>
      </article>
    </template>
  </section>
</template>
