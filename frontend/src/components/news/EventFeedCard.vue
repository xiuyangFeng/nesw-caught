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

const watchlistHits = computed(() =>
  (props.event.watchlist_hits ?? []).filter((hit): hit is string => Boolean(hit && hit.trim())),
);

const watchlistHitPreview = computed(() => watchlistHits.value.slice(0, 2));
const watchlistHitOverflow = computed(() => Math.max(0, watchlistHits.value.length - watchlistHitPreview.value.length));

const emit = defineEmits<{
  'open-event': [eventKey: string];
  'open-story': [id: number];
}>();
</script>

<template>
  <article class="event-feed-card event-feed-card--compact" data-role="event-feed-card">
    <button
      class="event-feed-card__primary"
      type="button"
      data-role="event-card-primary"
      :aria-label="`查看事件 ${event.event_title}`"
      @click="emit('open-event', event.event_key)"
    >
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
    </button>

    <div v-if="watchlistHitPreview.length" class="event-feed-card__watchlist-strip" data-role="event-card-watchlist-hits">
      <span class="event-feed-card__watchlist-strip-label">命中持仓：</span>
      <span
        v-for="hit in watchlistHitPreview"
        :key="hit"
        class="event-feed-card__watchlist-hit"
      >
        {{ hit }}
      </span>
      <span v-if="watchlistHitOverflow > 0" class="event-feed-card__watchlist-hit event-feed-card__watchlist-hit--overflow">
        +{{ watchlistHitOverflow }}
      </span>
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
          @click.stop="emit('open-story', item.id)"
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
  border-radius: var(--r-lg);
  border: 1px solid var(--border);
  background: var(--panel);
}

.event-feed-card:hover {
  border-color: var(--border-strong);
}

.event-feed-card__primary {
  display: grid;
  gap: 10px;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.event-feed-card__primary:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 6px;
  border-radius: var(--r-md);
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
  padding: 4px 9px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.event-feed-card__time,
.event-feed-card__label {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.event-feed-card__time {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
}

.market-tag {
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
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
  padding-top: 8px;
  border-top: 1px solid var(--border);
}

.event-feed-card__watchlist-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  color: var(--text-soft);
  font-size: 11px;
  line-height: 1.2;
}

.event-feed-card__watchlist-strip-label {
  flex: none;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.event-feed-card__watchlist-hit {
  flex: none;
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-feed-card__watchlist-hit--overflow {
  background: var(--panel-strong);
  color: var(--text-soft);
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
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--panel-strong);
  color: var(--text-soft);
  font-size: 11px;
  line-height: 1;
  padding: 6px 9px;
  cursor: pointer;
  transition: border-color 140ms ease, color 140ms ease;
}

.event-feed-card__story:hover {
  border-color: var(--border-strong);
  color: var(--text);
}

.event-feed-card__stats strong {
  color: var(--text);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 15px;
  font-weight: 640;
}

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
