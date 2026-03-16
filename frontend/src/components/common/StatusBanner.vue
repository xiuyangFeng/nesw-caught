<script setup lang="ts">
defineProps<{
  title: string;
  tone?: 'default' | 'warning' | 'danger' | 'success';
  detail?: string;
}>();
</script>

<template>
  <section class="status-banner" :data-tone="tone ?? 'default'">
    <div>
      <strong>{{ title }}</strong>
      <p v-if="detail">{{ detail }}</p>
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
  border-radius: 18px;
  border: 1px solid var(--border);
  background: rgba(255, 251, 245, 0.92);
}

.status-banner p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--muted);
}

.status-banner[data-tone='warning'] {
  border-color: rgba(166, 111, 18, 0.24);
  background: rgba(252, 244, 224, 0.96);
}

.status-banner[data-tone='danger'] {
  border-color: rgba(181, 73, 47, 0.24);
  background: rgba(252, 236, 232, 0.96);
}

.status-banner[data-tone='success'] {
  border-color: rgba(15, 123, 108, 0.24);
  background: rgba(232, 247, 243, 0.96);
}
</style>
