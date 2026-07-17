<script setup lang="ts">
import type { NewsFeedTopic } from '../../types/api';

defineProps<{ topics: NewsFeedTopic[] }>();

const emit = defineEmits<{ 'open-topic': [id: number] }>();

function topicLabel(topic: NewsFeedTopic): string {
  return topic.display_name?.trim() || topic.topic_title;
}

function topicTitleAttr(topic: NewsFeedTopic): string | undefined {
  const alias = topic.alias_zh?.trim();
  if (alias) {
    return alias;
  }
  const display = topic.display_name?.trim();
  if (display && display !== topic.topic_title) {
    return topic.topic_title;
  }
  return undefined;
}
</script>

<template>
  <div class="topic-chips" data-role="topic-chips-row">
    <span class="topic-chips__label">主题</span>
    <p v-if="!topics.length" class="topic-chips__empty">暂无主题</p>
    <div v-else class="topic-chips__scroller">
      <button
        v-for="topic in topics"
        :key="topic.id"
        type="button"
        class="topic-chip"
        data-role="topic-chip"
        :title="topicTitleAttr(topic)"
        @click="emit('open-topic', topic.id)"
      >
        {{ topicLabel(topic) }}
        <span class="topic-chip__count">({{ topic.news_count }})</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.topic-chips {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.topic-chips__label {
  flex: none;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.topic-chips__empty {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

.topic-chips__scroller {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: thin;
  padding-bottom: 2px;
  min-width: 0;
}

.topic-chip {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 11px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--panel-strong);
  color: var(--text-soft);
  font-size: 12px;
  line-height: 1.2;
  cursor: pointer;
  transition: border-color 140ms ease, color 140ms ease;
}

.topic-chip:hover {
  border-color: var(--border-strong);
  color: var(--text);
}

.topic-chip__count {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
}
</style>
