<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string;
  compact?: boolean;
  eyebrow?: string;
}>();
</script>

<template>
  <section class="surface section-card" :class="{ compact }">
    <header>
      <div>
        <p v-if="eyebrow" class="section-eyebrow" data-role="section-eyebrow">{{ eyebrow }}</p>
        <h2>{{ title }}</h2>
        <p v-if="subtitle" class="section-subtitle">{{ subtitle }}</p>
      </div>
      <slot name="actions" />
    </header>
    <div class="section-content">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.section-card {
  border-radius: 18px;
  padding: 20px;
}

.section-card.compact {
  padding: 16px 18px;
}

header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

h2 {
  margin: 0;
  font-size: 18px;
  line-height: 1.3;
  letter-spacing: -0.02em;
}

.section-eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--system);
}

.section-subtitle {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 13px;
}
</style>
