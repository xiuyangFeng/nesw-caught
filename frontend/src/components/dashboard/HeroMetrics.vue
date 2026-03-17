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
      <p data-role="metric-label">{{ metric.label }}</p>
      <strong data-role="metric-value">{{ metric.value }}</strong>
      <span data-role="metric-note">{{ metric.note }}</span>
    </article>
  </section>
</template>

<style scoped>
.hero-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.hero-card {
  border-radius: 18px;
  padding: 18px;
}

.hero-card p,
.hero-card span {
  margin: 0;
  color: var(--muted);
}

.hero-card p {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
}

.hero-card strong {
  display: block;
  margin: 8px 0 6px;
  font-size: 32px;
  letter-spacing: -0.04em;
}

.hero-card[data-tone='positive'] strong {
  color: var(--positive);
}

.hero-card[data-tone='negative'] strong {
  color: var(--negative);
}

@media (max-width: 1320px) {
  .hero-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .hero-grid {
    grid-template-columns: 1fr;
  }
}
</style>
