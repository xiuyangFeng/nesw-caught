<script setup lang="ts">
import { computed, ref, watch } from 'vue';
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
const eventKey = computed(() => String(route.params.eventKey ?? ''));

const sortedNewsItems = computed(() =>
  [...(eventDetail.value?.news_items ?? [])].sort((left, right) => {
    const rightTime = Date.parse(getNewsDisplayTimestamp(right) ?? '');
    const leftTime = Date.parse(getNewsDisplayTimestamp(left) ?? '');
    const normalizedRight = Number.isNaN(rightTime) ? 0 : rightTime;
    const normalizedLeft = Number.isNaN(leftTime) ? 0 : leftTime;
    if (normalizedRight !== normalizedLeft) {
      return normalizedRight - normalizedLeft;
    }
    return right.id - left.id;
  }),
);

async function loadEventDetail() {
  loading.value = true;
  errorState.value = null;
  eventDetail.value = null;
  try {
    const response = await apiClient.getNewsEventDetail(eventKey.value);
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

watch(
  () => eventKey.value,
  async () => {
    await loadEventDetail();
  },
  { immediate: true },
);
</script>

<template>
  <div class="grid gap-4">
    <header class="grid gap-2">
      <button
        class="inline-flex w-fit items-center gap-2 rounded-full border border-border bg-panel-soft px-3 py-1.5 text-sm text-text-soft transition hover:border-system/40 hover:text-text"
        type="button"
        data-role="event-detail-back"
        @click="backToFeed"
      >
        返回 Latest Events
      </button>
      <div>
        <h1 class="page-title">Event Detail</h1>
        <p class="page-subtitle">查看当前事件卡挂载的新闻时间线和摘要信息。</p>
      </div>
    </header>

    <LoadingBlock
      :loading="loading"
      :empty="!eventDetail"
      loading-text="正在加载事件详情"
      :empty-text="errorState === 'not-found' ? '事件已不存在，或已发生聚合变化' : '加载事件详情失败'"
    >
      <div v-if="eventDetail" class="grid gap-4">
        <SectionCard :title="eventDetail.event_title" :subtitle="eventDetail.event_summary ?? '事件摘要待补充'">
          <div class="flex flex-wrap gap-2 text-muted">
            <span class="event-pill">{{ eventDetail.event_type }}</span>
            <span class="pill" :class="eventDetail.sentiment_label">{{ sentimentText(eventDetail.sentiment_label) }}</span>
            <span>{{ eventDetail.market.toUpperCase() }}</span>
            <span>{{ eventDetail.primary_symbol ?? 'N/A' }}</span>
            <span>{{ eventDetail.related_symbols.join(' · ') || '未关联股票' }}</span>
            <span>Sources {{ eventDetail.source_count }}</span>
            <span>News {{ eventDetail.news_count }}</span>
            <span>
              {{ eventDetail.last_seen_at ? `${formatMarketTime(eventDetail.last_seen_at, eventDetail.market)} ${getMarketTimezoneLabel(eventDetail.market)}` : '时间待补' }}
            </span>
          </div>
        </SectionCard>

        <SectionCard title="Timeline" subtitle="只展示当前事件挂载的新闻，按时间倒序排列。">
          <div class="grid gap-3">
            <article
              v-for="item in sortedNewsItems"
              :key="item.id"
              class="grid gap-2 rounded-[18px] border border-border bg-panel-soft px-4 py-4"
            >
              <div class="flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="pill neutral">{{ item.source_name }}</span>
                  <span>{{ formatMarketTime(getNewsDisplayTimestamp(item), item.market) }} {{ getMarketTimezoneLabel(item.market) }}</span>
                </div>
              </div>
              <h2 class="m-0 text-lg text-text" data-role="event-timeline-title">{{ item.title }}</h2>
              <p class="m-0 text-sm leading-[1.6] text-muted">{{ item.summary ?? '摘要待补充' }}</p>
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
</style>
