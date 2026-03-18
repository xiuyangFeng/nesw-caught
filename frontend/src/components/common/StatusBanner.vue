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
  background: var(--panel-soft);
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
  border-color: rgba(83, 194, 255, 0.2);
  background: linear-gradient(180deg, rgba(15, 27, 40, 0.96), rgba(11, 20, 31, 0.96));
}

.status-banner[data-tone='danger'] {
  border-color: rgba(255, 111, 134, 0.28);
  background: linear-gradient(180deg, rgba(31, 17, 24, 0.92), rgba(18, 11, 17, 0.94));
}

.status-banner[data-tone='success'] {
  border-color: rgba(57, 200, 132, 0.24);
  background: linear-gradient(180deg, rgba(11, 28, 22, 0.92), rgba(10, 18, 15, 0.94));
}
</style>
