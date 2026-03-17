<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string;
  compact?: boolean;
}>();
</script>

<template>
  <section class="surface section-card" :class="{ compact }">
    <header>
      <div>
        <h2>{{ title }}</h2>
        <p v-if="subtitle">{{ subtitle }}</p>
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
  border-radius: 24px;
  padding: 22px;
}

.section-card.compact {
  padding: 18px 20px;
}

header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

h2 {
  margin: 0;
  font-size: 18px;
  line-height: 1.3;
}

p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 13px;
}
</style>
