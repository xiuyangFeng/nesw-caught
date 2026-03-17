<script setup lang="ts">
defineProps<{
  title: string;
  tone?: 'default' | 'warning' | 'danger' | 'success';
  detail?: string;
  kicker?: string;
}>();
</script>

<template>
  <section class="status-banner" :data-tone="tone ?? 'default'">
    <div>
      <p v-if="kicker" class="status-kicker" data-role="status-kicker">{{ kicker }}</p>
      <strong>{{ title }}</strong>
      <p v-if="detail" data-role="status-detail">{{ detail }}</p>
    </div>
    <slot />
  </section>
</template>

<style scoped>
.status-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.03);
}

.status-kicker {
  margin: 0 0 4px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--system);
}

.status-banner p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--muted);
}

.status-banner[data-tone='warning'] {
  border-color: rgba(255, 159, 47, 0.24);
  background: rgba(255, 159, 47, 0.08);
}

.status-banner[data-tone='danger'] {
  border-color: rgba(255, 127, 127, 0.24);
  background: rgba(255, 127, 127, 0.08);
}

.status-banner[data-tone='success'] {
  border-color: rgba(45, 201, 129, 0.24);
  background: rgba(45, 201, 129, 0.08);
}
</style>
