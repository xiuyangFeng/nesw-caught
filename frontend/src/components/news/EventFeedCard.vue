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

const compactSources = computed(() => {
  const sources = [...new Set(props.event.news_items.map((item) => item.source_name))].slice(0, 3);
  return sources.length ? sources.join(' · ') : '暂无来源';
});

const emit = defineEmits<{
  open: [id: number];
}>();
</script>

<template>
  <article class="event-feed-card event-feed-card--compact" data-role="event-feed-card">
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
        <p class="event-feed-card__meta-line">
          <span>{{ event.primary_symbol ?? 'N/A' }}</span>
          <span>{{ event.related_symbols.join(' · ') || '未关联' }}</span>
        </p>
      </div>

      <div class="event-feed-card__stats">
        <div>
          <span class="event-feed-card__label">Sources</span>
          <strong>{{ event.source_count }}</strong>
        </div>
        <div>
          <span class="event-feed-card__label">News</span>
          <strong>{{ event.news_count }}</strong>
        </div>
      </div>
    </div>

    <div class="event-feed-card__foot">
      <div class="event-feed-card__foot-copy">
        <span class="event-feed-card__label">Evidence</span>
        <strong>{{ compactSources }}</strong>
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
          {{ item.source_name }}
        </button>
      </div>
    </div>
  </article>
</template>

<style scoped>
.event-feed-card {
  display: grid;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(133, 161, 191, 0.18);
  background:
    radial-gradient(circle at top right, rgba(92, 174, 255, 0.18), transparent 28%),
    linear-gradient(180deg, rgba(11, 18, 28, 0.98), rgba(7, 12, 20, 0.98));
}

.event-feed-card--compact {
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}

.event-feed-card__head,
.event-feed-card__body {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.event-feed-card__kickers {
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
  gap: 6px;
  max-width: 720px;
}

.event-feed-card__meta-line,
.event-feed-card__foot strong {
  margin: 0;
  color: var(--text-soft);
  font-size: 13px;
  line-height: 1.4;
}

.event-feed-card__meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.event-feed-card__meta-line span + span {
  color: var(--text);
}

.event-feed-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-top: 2px;
  border-top: 1px solid rgba(133, 161, 191, 0.12);
}

.event-feed-card__foot-copy {
  display: grid;
  gap: 2px;
}

.event-feed-card__stats {
  display: grid;
  gap: 8px;
  min-width: 132px;
  justify-items: end;
}

.event-feed-card__stories {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.event-feed-card__story {
  border: 1px solid rgba(133, 161, 191, 0.16);
  border-radius: 999px;
  background: rgba(7, 12, 20, 0.72);
  color: var(--text-soft);
  font-size: 11px;
  line-height: 1;
  padding: 6px 9px;
}

.event-feed-card__stats strong,
.event-feed-card__foot strong {
  color: var(--text);
  font-weight: 600;
}

@media (max-width: 860px) {
  .event-feed-card__head,
  .event-feed-card__body {
    display: grid;
  }

  .event-feed-card__stats {
    min-width: 0;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    justify-items: start;
  }

  .event-feed-card__foot {
    flex-direction: column;
    align-items: flex-start;
  }

  .event-feed-card__stories {
    justify-content: flex-start;
  }
}
</style>
