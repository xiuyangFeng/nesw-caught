<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string;
}>();
</script>

<template>
  <section class="surface section-card">
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
}

p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 13px;
}
</style>
