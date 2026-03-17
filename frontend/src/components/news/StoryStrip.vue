<script setup lang="ts">
import type { EditorialStoryEntry } from '../../utils/newsEditorial';
import NewsCard from './NewsCard.vue';

defineProps<{
  title: string;
  stories: EditorialStoryEntry[];
}>();

const emit = defineEmits<{
  open: [id: number];
}>();
</script>

<template>
  <section class="story-strip">
    <header class="strip-header">
      <h2>{{ title }}</h2>
    </header>
    <div class="strip-grid">
      <NewsCard
        v-for="story in stories"
        :key="story.item.id"
        :entry="story"
        variant="supporting"
        @open="emit('open', $event)"
      />
    </div>
  </section>
</template>

<style scoped>
.story-strip {
  display: grid;
  gap: 14px;
}

.strip-header h2 {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--neutral);
}

.strip-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 1099px) {
  .strip-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .strip-grid {
    grid-template-columns: 1fr;
  }
}
</style>
