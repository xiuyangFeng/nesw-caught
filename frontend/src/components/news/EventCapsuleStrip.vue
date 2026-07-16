<script setup lang="ts">
import { sentimentText } from '../../utils/format';
import type { NewsFeedEventCard } from '../../types/api';

defineProps<{ events: NewsFeedEventCard[] }>();

const emit = defineEmits<{ 'open-event': [eventKey: string] }>();
</script>

<template>
  <div class="capsule-strip" data-role="event-capsule-strip">
    <span class="capsule-strip__label">事件雷达</span>
    <p v-if="!events.length" class="capsule-strip__empty">暂无聚合事件</p>
    <div v-else class="capsule-strip__scroller">
      <button
        v-for="event in events"
        :key="event.event_key"
        type="button"
        class="capsule"
        data-role="event-capsule"
        :aria-label="`查看事件 ${event.event_title}`"
        @click="emit('open-event', event.event_key)"
      >
        <span class="capsule__type">{{ event.event_type }}</span>
        <span
          class="capsule__dot"
          :class="event.sentiment_label"
          :title="sentimentText(event.sentiment_label)"
        ></span>
        <span class="capsule__market">{{ event.market.toUpperCase() }}</span>
        <span class="capsule__title">{{ event.event_title }}</span>
        <span v-if="(event.watchlist_hits ?? []).length" class="capsule__hits">
          持仓 {{ (event.watchlist_hits ?? []).length }}
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.capsule-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.capsule-strip__label {
  flex: none;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.capsule-strip__empty {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

.capsule-strip__scroller {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: thin;
  padding-bottom: 2px;
  min-width: 0;
}

.capsule {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 340px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--panel-strong);
  color: var(--text-soft);
  font-size: 12px;
  line-height: 1.2;
  cursor: pointer;
  transition: border-color 140ms ease, color 140ms ease;
}

.capsule:hover {
  border-color: var(--border-strong);
  color: var(--text);
}

.capsule__type {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.capsule__dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--accent);
}

.capsule__dot.positive {
  background: var(--positive);
}

.capsule__dot.negative {
  background: var(--negative);
}

.capsule__market {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.08em;
}

.capsule__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text);
}

.capsule__hits {
  flex: none;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 10.5px;
}
</style>
