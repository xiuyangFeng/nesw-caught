<script setup lang="ts">
defineProps<{
  metrics: Array<{
    label: string;
    value: string;
    note: string;
    tone: 'default' | 'positive' | 'negative';
  }>;
}>();
</script>

<template>
  <section class="hero-grid">
    <article v-for="metric in metrics" :key="metric.label" class="surface hero-card" :data-tone="metric.tone">
      <p>{{ metric.label }}</p>
      <strong>{{ metric.value }}</strong>
      <span>{{ metric.note }}</span>
    </article>
  </section>
</template>

<style scoped>
.hero-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.hero-card {
  border-radius: 24px;
  padding: 22px;
}

.hero-card p,
.hero-card span {
  margin: 0;
  color: var(--muted);
}

.hero-card strong {
  display: block;
  margin: 10px 0 8px;
  font-size: 34px;
  letter-spacing: -0.04em;
}

.hero-card[data-tone='positive'] strong {
  color: var(--positive);
}

.hero-card[data-tone='negative'] strong {
  color: var(--negative);
}
</style>
