<script setup lang="ts">
import { computed } from 'vue';

import { sentimentText } from '../../utils/format';
import { formatMarketTime, getMarketTimezoneLabel } from '../../utils/time';
import type { NewsFeedEventCard } from '../../types/api';

const props = defineProps<{
  event: NewsFeedEventCard;
}>();

const seenLabel = computed(() => {
  if (!props.event.last_seen_at) {
    return '时间待补';
  }
  return `${formatMarketTime(props.event.last_seen_at, props.event.market)} ${getMarketTimezoneLabel(props.event.market)}`;
});

const emit = defineEmits<{
  open: [id: number];
}>();
</script>

<template>
  <article class="event-feed-card" data-role="event-feed-card">
    <div class="event-feed-card__head">
      <div class="event-feed-card__kickers">
        <span class="event-pill">{{ event.event_type }}</span>
        <span class="pill" :class="event.sentiment_label">{{ sentimentText(event.sentiment_label) }}</span>
        <span class="market-tag">{{ event.market.toUpperCase() }}</span>
      </div>
      <span class="event-feed-card__time">{{ seenLabel }}</span>
    </div>

    <div class="event-feed-card__body">
      <div class="event-feed-card__copy">
        <h3 data-role="event-card-title">{{ event.event_title }}</h3>
        <p class="event-feed-card__summary">{{ event.event_summary ?? '摘要待补充' }}</p>
      </div>

      <div class="event-feed-card__stats">
        <div>
          <span class="event-feed-card__label">Primary</span>
          <strong>{{ event.primary_symbol ?? 'N/A' }}</strong>
        </div>
        <div>
          <span class="event-feed-card__label">Symbols</span>
          <strong>{{ event.related_symbols.join(' · ') || '未关联' }}</strong>
        </div>
        <div>
          <span class="event-feed-card__label">Sources</span>
          <strong>{{ event.source_count }}</strong>
        </div>
      </div>
    </div>

    <div class="event-feed-card__stories">
      <button
        v-for="item in event.news_items"
        :key="item.id"
        class="event-feed-card__story"
        type="button"
        data-role="event-card-story"
        @click="emit('open', item.id)"
      >
        <span>{{ item.source_name }}</span>
        <strong>{{ item.title }}</strong>
      </button>
    </div>
  </article>
</template>

<style scoped>
.event-feed-card {
  display: grid;
  gap: 14px;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(133, 161, 191, 0.18);
  background:
    radial-gradient(circle at top right, rgba(92, 174, 255, 0.18), transparent 28%),
    linear-gradient(180deg, rgba(11, 18, 28, 0.98), rgba(7, 12, 20, 0.98));
}

.event-feed-card__head,
.event-feed-card__body {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.event-feed-card__kickers,
.event-feed-card__stories {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.event-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(92, 174, 255, 0.14);
  color: #9fd0ff;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.event-feed-card__time,
.event-feed-card__label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.event-feed-card__copy {
  display: grid;
  gap: 8px;
  max-width: 720px;
}

.event-feed-card__summary {
  margin: 0;
  color: var(--text-soft);
  line-height: 1.65;
}

.event-feed-card__stats {
  display: grid;
  gap: 10px;
  min-width: 180px;
}

.event-feed-card__stats strong,
.event-feed-card__story strong {
  color: var(--text);
  font-weight: 600;
}

.event-feed-card__story {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(133, 161, 191, 0.14);
  background: rgba(7, 12, 20, 0.72);
  text-align: left;
}

.event-feed-card__story span {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

@media (max-width: 860px) {
  .event-feed-card__head,
  .event-feed-card__body {
    display: grid;
  }

  .event-feed-card__stats {
    min-width: 0;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
