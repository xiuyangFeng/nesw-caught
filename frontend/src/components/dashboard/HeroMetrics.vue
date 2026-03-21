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
        class="surface block rounded-[18px] p-[18px] transition duration-150 ease-out hover:-translate-y-px hover:border-[#3aa9f59e] hover:bg-[rgba(15,39,61,0.92)]"
        data-role="metric-link"
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
      </RouterLink>

      <article
        v-else
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
    </template>
  </section>
</template>
