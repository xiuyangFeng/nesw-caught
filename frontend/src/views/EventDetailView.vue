<script setup lang="ts">
import { ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { apiClient } from '../api/client';
import { HttpError } from '../api/http';
import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import type { NewsEventDetail } from '../types/api';
import { sentimentText } from '../utils/format';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../utils/time';

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const errorState = ref<'not-found' | 'error' | null>(null);
const eventDetail = ref<NewsEventDetail | null>(null);
const eventKey = () => String(route.params.eventKey ?? '');

function eventStageLabel(index: number) {
  if (index === 0) {
    return '首发';
  }
  if (index === 1) {
    return '跟进';
  }
  return '更新';
}

async function loadEventDetail() {
  loading.value = true;
  errorState.value = null;
  eventDetail.value = null;
  try {
    const response = await apiClient.getNewsEventDetail(eventKey());
    eventDetail.value = response.data;
  } catch (error) {
    if (error instanceof HttpError && error.status === 404) {
      errorState.value = 'not-found';
    } else {
      errorState.value = 'error';
    }
  } finally {
    loading.value = false;
  }
}

function backToFeed() {
  router.push({ name: 'news-feed' });
}

function openNewsDetail(newsId: number) {
  router.push({ name: 'news-detail', params: { id: newsId } });
}

watch(
  () => eventKey(),
  async () => {
    await loadEventDetail();
  },
  { immediate: true },
);
</script>

<template>
  <div class="grid gap-4">
    <header class="flex justify-start">
      <button
        class="inline-flex w-fit items-center gap-2 rounded-full border border-border bg-panel-soft px-3 py-1.5 text-sm text-text-soft transition hover:border-system/40 hover:text-text"
        type="button"
        data-role="event-detail-back"
        @click="backToFeed"
      >
        返回 Latest Events
      </button>
    </header>

    <LoadingBlock
      :loading="loading"
      :empty="!eventDetail"
      loading-text="正在加载事件详情"
      :empty-text="errorState === 'not-found' ? '事件已不存在，或已发生聚合变化' : '加载事件详情失败'"
    >
      <div v-if="eventDetail" class="grid gap-4">
        <section
          data-role="event-detail-header"
          class="grid gap-4 overflow-hidden rounded-[26px] border border-border bg-[linear-gradient(180deg,rgba(18,26,43,0.96),rgba(10,14,24,0.94))] px-5 py-5 shadow-[0_18px_50px_rgba(0,0,0,0.28)]"
        >
          <div class="grid gap-2">
            <div class="flex flex-wrap items-center gap-2 text-muted">
              <span class="event-pill">{{ eventDetail.event_type.toUpperCase() }}</span>
              <span class="pill" :class="eventDetail.sentiment_label">{{ sentimentText(eventDetail.sentiment_label) }}</span>
              <span>{{ eventDetail.market.toUpperCase() }}</span>
              <span>{{ eventDetail.primary_symbol ?? 'N/A' }}</span>
            </div>
            <div>
              <h1 class="m-0 text-[clamp(1.9rem,4vw,3rem)] font-semibold tracking-[-0.04em] text-text">
                {{ eventDetail.event_title }}
              </h1>
              <p class="mt-2 max-w-4xl text-[15px] leading-[1.7] text-muted">
                {{ eventDetail.event_summary ?? '事件摘要待补充' }}
              </p>
            </div>
          </div>

          <div class="flex flex-wrap gap-2 text-[13px] text-muted">
            <span class="metric-chip">{{ eventDetail.related_symbols.join(' · ') || '未关联股票' }}</span>
            <span class="metric-chip">Sources {{ eventDetail.source_count }}</span>
            <span class="metric-chip">News {{ eventDetail.news_count }}</span>
            <span class="metric-chip">
              {{ eventDetail.last_seen_at ? `${formatMarketTime(eventDetail.last_seen_at, eventDetail.market)} ${getMarketTimezoneLabel(eventDetail.market)}` : '时间待补' }}
            </span>
          </div>
        </section>

        <SectionCard title="Timeline" subtitle="按事件演化顺序展示当前挂载新闻。">
          <div class="grid gap-4">
            <article
              v-for="(item, index) in eventDetail.news_items"
              :key="item.id"
              class="timeline-row"
            >
              <div class="timeline-rail">
                <span class="timeline-node" />
                <span class="timeline-line" :class="{ 'is-hidden': index === eventDetail.news_items.length - 1 }" />
              </div>

              <div class="timeline-card">
                <div class="timeline-meta-row flex flex-wrap items-center gap-2 text-sm text-muted">
                  <span data-role="event-stage-label" class="stage-pill">{{ eventStageLabel(index) }}</span>
                  <span data-role="event-source-name" class="pill neutral">{{ item.source_name }}</span>
                  <span data-role="event-sentiment-pill" class="pill" :class="item.sentiment_label">{{ sentimentText(item.sentiment_label) }}</span>
                  <span>{{ formatMarketTime(getNewsDisplayTimestamp(item), item.market) }} {{ getMarketTimezoneLabel(item.market) }}</span>
                </div>

                <h2 class="timeline-title m-0 text-text" data-role="event-timeline-title">{{ item.title }}</h2>
                <p class="timeline-summary m-0 text-muted" data-role="event-timeline-summary-compact">
                  {{ item.summary ?? '摘要待补充' }}
                </p>

                <div class="timeline-actions flex flex-wrap gap-2">
                  <button
                    type="button"
                    data-role="event-open-news-detail"
                    class="timeline-action timeline-action-compact timeline-action-primary"
                    @click="openNewsDetail(item.id)"
                  >
                    查看新闻详情
                  </button>
                  <a
                    v-if="item.canonical_url"
                    :href="item.canonical_url"
                    target="_blank"
                    rel="noreferrer"
                    data-role="event-open-source-link"
                    class="timeline-action timeline-action-compact"
                  >
                    打开原文
                  </a>
                </div>
              </div>
            </article>
          </div>
        </SectionCard>
      </div>
    </LoadingBlock>
  </div>
</template>

<style scoped>
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

.metric-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(132, 156, 189, 0.18);
  background: rgba(255, 255, 255, 0.04);
}

.timeline-row {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 10px;
}

.timeline-rail {
  display: grid;
  justify-items: center;
  grid-template-rows: auto 1fr;
}

.timeline-node {
  width: 9px;
  height: 9px;
  margin-top: 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #9fd0ff, #2d7dd2);
  box-shadow: 0 0 0 4px rgba(92, 174, 255, 0.12);
}

.timeline-line {
  width: 1px;
  min-height: 100%;
  background: linear-gradient(180deg, rgba(159, 208, 255, 0.28), rgba(159, 208, 255, 0));
}

.timeline-line.is-hidden {
  opacity: 0;
}

.timeline-card {
  display: grid;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 18px;
  border: 1px solid rgba(132, 156, 189, 0.16);
  background: linear-gradient(180deg, rgba(17, 24, 39, 0.86), rgba(12, 18, 30, 0.92));
}

.timeline-meta-row {
  row-gap: 6px;
  column-gap: 6px;
  font-size: 12px;
}

.timeline-title {
  font-size: 15px;
  line-height: 1.32;
  font-weight: 550;
}

.timeline-summary {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  line-height: 1.35;
}

.timeline-actions {
  row-gap: 6px;
  column-gap: 8px;
}

.stage-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 9px;
  border-radius: 999px;
  background: rgba(249, 196, 88, 0.14);
  color: #f3cf7a;
  font-size: 10px;
  letter-spacing: 0.08em;
}

.timeline-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(132, 156, 189, 0.18);
  background: rgba(255, 255, 255, 0.04);
  color: var(--color-text-soft);
  font-size: 12px;
  text-decoration: none;
  transition: border-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.timeline-action:hover {
  border-color: rgba(159, 208, 255, 0.34);
  color: var(--color-text);
  transform: translateY(-1px);
}

.timeline-action-primary {
  background: linear-gradient(135deg, rgba(23, 104, 194, 0.95), rgba(58, 169, 245, 0.95));
  color: white;
  border-color: transparent;
}

@media (max-width: 640px) {
  .timeline-row {
    grid-template-columns: 16px minmax(0, 1fr);
    gap: 8px;
  }

  .timeline-card {
    padding: 10px;
  }

  .timeline-title {
    font-size: 14px;
  }

  .timeline-summary {
    font-size: 11px;
  }
}
</style>
