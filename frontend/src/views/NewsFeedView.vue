<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import EventFeedCard from '../components/news/EventFeedCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import NewsCard from '../components/news/NewsCard.vue';
import NewsVirtualList from '../components/news/NewsVirtualList.vue';
import { useConnectionStore } from '../stores/connectionStore';
import { useNewsStore } from '../stores/newsStore';
import type { Market, SentimentLabel } from '../types/api';
import type { EditorialStoryEntry } from '../utils/newsEditorial';
import { rankEditorialStories } from '../utils/newsEditorial';

const newsStore = useNewsStore();
const connectionStore = useConnectionStore();
const router = useRouter();
const VIRTUAL_LIST_THRESHOLD = 30;
const FEED_LAYOUT_STREAM_LIMIT = 100;
const filters = reactive<{
  market: Market | '';
  sentiment_label: SentimentLabel | '';
  q: string;
}>({
  market: '',
  sentiment_label: '',
  q: '',
});

function matchesFilters(item: { market: Market; sentiment_label: SentimentLabel; source_name?: string; title?: string; summary?: string | null }) {
  if (filters.market && item.market !== filters.market) {
    return false;
  }
  if (filters.sentiment_label && item.sentiment_label !== filters.sentiment_label) {
    return false;
  }
  if (selectedSource.value && item.source_name && item.source_name !== selectedSource.value) {
    return false;
  }
  if (filters.q) {
    const haystack = `${item.title ?? ''} ${item.summary ?? ''}`.toLowerCase();
    if (!haystack.includes(filters.q.toLowerCase())) {
      return false;
    }
  }
  return true;
}

const feedStreamItems = computed(() => {
  return newsStore.feedItems.filter((item) => matchesFilters(item));
});
const filteredEvents = computed(() =>
  (newsStore.feedLayoutDegraded ? [] : newsStore.feedLayout.events).filter((event) =>
    filters.market && event.market !== filters.market
      ? false
      : event.news_items.some((item) => matchesFilters(item)) || (!filters.q && !selectedSource.value && !filters.sentiment_label),
  ),
);
const filteredTopics = computed(() =>
  (newsStore.feedLayoutDegraded ? [] : newsStore.feedLayout.topics).filter((topic) => {
    if (filters.market && topic.market !== filters.market) {
      return false;
    }
    if (filters.sentiment_label && topic.sentiment_label !== filters.sentiment_label) {
      return false;
    }
    if (selectedSource.value) {
      return false;
    }
    if (filters.q) {
      const haystack = `${topic.topic_title} ${topic.topic_summary ?? ''} ${topic.keywords.join(' ')}`.toLowerCase();
      if (!haystack.includes(filters.q.toLowerCase())) {
        return false;
      }
    }
    return true;
  }),
);
const sourceOptions = computed(() => [
  ...new Set(newsStore.feedItems.map((item) => item.source_name)),
]);
const hasVisibleFeedContent = computed(() => filteredEvents.value.length > 0 || filteredTopics.value.length > 0 || feedStreamItems.value.length > 0);
const selectedSource = ref('');
const hydratingIds = new Set<number>();
const degradedSourceCount = computed(() =>
  newsStore.sourceHealth.filter((item) => item.status === 'degraded' || item.status === 'offline').length,
);
const runtimeBannerTitle = computed(() => {
  if (connectionStore.state === 'offline' || connectionStore.state === 'degraded') {
    return '实时连接异常';
  }
  const status = newsStore.newsRuntimeStatus?.feed_status;
  if (status === 'degraded') {
    return '新闻供给降级';
  }
  if (status === 'delayed') {
    return '新闻更新延迟';
  }
  return '新闻供给正常';
});
const runtimeBannerTone = computed(() => {
  if (connectionStore.state === 'offline' || connectionStore.state === 'degraded') {
    return 'danger';
  }
  const status = newsStore.newsRuntimeStatus?.feed_status;
  if (status === 'degraded') {
    return 'danger';
  }
  if (status === 'delayed') {
    return 'warning';
  }
  return 'success';
});
const runtimeBannerDetail = computed(() => {
  const recentFlow = newsStore.lastIncrementalAt ?? '无';
  return `最近入流 ${recentFlow} · 异常来源 ${degradedSourceCount.value}`;
});
const visibleStreamIds = ref<number[]>([]);
const hydrationInFlight = ref(false);
const pendingHydrationPass = ref(false);
const hasLoadedDetail = (id: number) => Object.prototype.hasOwnProperty.call(newsStore.detailMap, id);
const layoutStreamScoreMap = computed(() => {
  if (newsStore.feedLayoutDegraded) {
    return new Map<number, number | null>();
  }
  return new Map(
    newsStore.feedLayout.stream
      .filter((item) => item.editorial_score != null)
      .map((item) => [item.id, item.editorial_score ?? null]),
  );
});
const rankedFeedItems = computed(() =>
  newsStore.feedItems.map((item) => {
    const editorialScore = layoutStreamScoreMap.value.get(item.id);
    if (editorialScore == null) {
      return item;
    }
    return {
      ...item,
      editorial_score: editorialScore,
    };
  }),
);
const orderedEntries = computed<EditorialStoryEntry[]>(() =>
  rankEditorialStories(
    rankedFeedItems.value.filter((item) => matchesFilters(item)),
    newsStore.detailMap,
  ),
);
const useVirtualScrolling = computed(() => orderedEntries.value.length > VIRTUAL_LIST_THRESHOLD);
const orderedEntryIdSet = computed(() => new Set(orderedEntries.value.map((entry) => entry.item.id)));
const hydrationCandidateIds = computed(() => {
  const candidateIds = new Set<number>();
  orderedEntries.value.slice(0, 8).forEach((entry) => candidateIds.add(entry.item.id));
  visibleStreamIds.value
    .filter((id) => orderedEntryIdSet.value.has(id))
    .forEach((id) => candidateIds.add(id));
  return [...candidateIds].filter((id) => orderedEntryIdSet.value.has(id) && !hasLoadedDetail(id));
});

async function hydrateEditorialDetails() {
  if (hydrationInFlight.value) {
    pendingHydrationPass.value = true;
    return;
  }

  const idsToLoad = hydrationCandidateIds.value.filter((id) => !hydratingIds.has(id));

  if (!idsToLoad.length) {
    return;
  }

  hydrationInFlight.value = true;
  idsToLoad.forEach((id) => hydratingIds.add(id));
  try {
    await Promise.all(
      idsToLoad.map(async (id) => {
        try {
          await newsStore.loadDetail(id);
        } finally {
          hydratingIds.delete(id);
        }
      }),
    );
  } finally {
    hydrationInFlight.value = false;
    if (pendingHydrationPass.value) {
      pendingHydrationPass.value = false;
      await nextTick();
      await hydrateEditorialDetails();
    }
  }
}

watch(
  () => ({ ...filters, source_name: selectedSource.value }),
  async () => {
    await Promise.all([
      newsStore.loadFeedLayout({
        market: filters.market || undefined,
        limit_events: 6,
        limit_topics: 6,
        limit_stream: FEED_LAYOUT_STREAM_LIMIT,
      }),
      newsStore.loadFeedNews({
        ...filters,
        limit: 300,
      }),
    ]);
    await hydrateEditorialDetails();
  },
);

function openStory(id: number) {
  router.push({ name: 'news-detail', params: { id } });
}

onMounted(async () => {
  await Promise.all([
    newsStore.loadFeedLayout({ limit_events: 6, limit_topics: 6, limit_stream: FEED_LAYOUT_STREAM_LIMIT }),
    newsStore.loadFeedNews({ limit: 300 }),
  ]);
});

watch(hydrationCandidateIds, async (ids) => {
  if (!ids.length) {
    return;
  }
  await hydrateEditorialDetails();
}, { immediate: true });

watch(useVirtualScrolling, (enabled) => {
  if (!enabled) {
    visibleStreamIds.value = [];
  }
}, { immediate: true });
</script>

<template>
  <div class="grid gap-[14px]">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h1 class="page-title">Latest Events</h1>
        <p class="page-subtitle">Compact scan of the latest market events, then supporting topics and raw evidence.</p>
      </div>
      <StaleBadge :stale="newsStore.feedStale" label="新闻列表" />
    </header>

    <StatusBanner
      kicker="Runtime"
      :title="runtimeBannerTitle"
      :tone="runtimeBannerTone"
      :detail="runtimeBannerDetail"
    />

    <section class="surface grid gap-[18px] rounded-[22px] p-5" data-role="news-feed-shell">
      <div class="flex flex-col items-start justify-between gap-4 xl:flex-row">
        <div>
          <p class="mb-2 text-[11px] uppercase tracking-[0.2em] text-[#ffb77d]">News Feed</p>
          <h2 class="m-0 text-[30px] tracking-[-0.04em] text-text">Latest Events</h2>
          <p class="mt-2 max-w-[60ch] leading-[1.65] text-muted">
            先扫最新事件，再看主题簇和原始新闻流作为证据层。
          </p>
        </div>
        <div
          class="flex flex-wrap gap-2 rounded-[16px] border border-border bg-[linear-gradient(180deg,rgba(11,18,28,0.96),rgba(8,14,23,0.96))] p-2.5"
          data-role="filter-bar"
        >
          <select
            v-model="filters.market"
            class="min-w-[138px] rounded-xl border border-border bg-[rgba(6,11,19,0.92)] px-3 py-2.5 text-text"
          >
            <option value="">全部市场</option>
            <option value="cn">A股/国内</option>
            <option value="hk">港股</option>
            <option value="us">美股</option>
          </select>
          <select
            v-model="filters.sentiment_label"
            class="min-w-[138px] rounded-xl border border-border bg-[rgba(6,11,19,0.92)] px-3 py-2.5 text-text"
          >
            <option value="">全部情绪</option>
            <option value="positive">偏利好</option>
            <option value="negative">偏利空</option>
            <option value="neutral">中性</option>
          </select>
          <select
            v-model="selectedSource"
            class="min-w-[138px] rounded-xl border border-border bg-[rgba(6,11,19,0.92)] px-3 py-2.5 text-text"
          >
            <option value="">全部来源</option>
            <option v-for="source in sourceOptions" :key="source" :value="source">{{ source }}</option>
          </select>
          <input
            v-model="filters.q"
            class="min-w-[240px] rounded-xl border border-border bg-[rgba(6,11,19,0.92)] px-3 py-2.5 text-text max-xl:min-w-0"
            type="search"
            placeholder="搜索标题或摘要"
          />
        </div>
      </div>

      <LoadingBlock :loading="newsStore.feedLoading" :empty="!hasVisibleFeedContent">
        <SectionCard
          eyebrow="Lead Layer"
          title="Event Radar"
          subtitle="首页首屏先展示聚合后的市场事件主卡，卡片只保留事件级元数据。"
          compact
          data-role="event-radar-shell"
        >
          <div v-if="filteredEvents.length" class="grid gap-[14px]">
            <EventFeedCard
              v-for="event in filteredEvents"
              :key="event.event_key"
              :event="event"
              @open="openStory"
            />
          </div>
          <p v-else class="text-sm text-muted">Event Radar 暂无聚合事件</p>
        </SectionCard>

        <SectionCard
          eyebrow="Theme Layer"
          title="Topic Watch"
          subtitle="保留持续发酵的主题簇，用于观察主线扩散。"
          compact
          data-role="topic-watch-shell"
        >
          <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <article
              v-for="topic in filteredTopics"
              :key="topic.id"
              class="rounded-[14px] border border-border bg-[rgba(7,12,20,0.72)] p-4"
            >
              <div class="mb-2 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.08em] text-muted">
                <span>{{ topic.market.toUpperCase() }}</span>
                <span>{{ topic.sentiment_label }}</span>
              </div>
              <h3 class="m-0 text-base text-text">{{ topic.topic_title }}</h3>
              <p class="mt-2 text-sm leading-[1.6] text-muted">{{ topic.topic_summary ?? '主题摘要待补充' }}</p>
              <p class="mt-3 text-xs text-text-soft">{{ topic.related_symbols.join(' · ') || '未关联股票' }}</p>
            </article>
          </div>
        </SectionCard>

        <SectionCard
          eyebrow="Live Flow"
          title="Raw Stream"
          subtitle="保留原始新闻卡片作为证据层，优先级低于事件和主题。"
          compact
          data-role="news-stream-shell"
        >
          <NewsVirtualList
            v-if="useVirtualScrolling"
            :entries="orderedEntries"
            @open="openStory"
            @visible-ids="visibleStreamIds = $event"
          />
          <div v-else class="grid grid-cols-1 gap-[14px]" data-role="news-stream-list">
            <NewsCard
              v-for="entry in orderedEntries"
              :key="entry.item.id"
              :entry="entry"
              variant="stream-compact"
              @open="openStory"
            />
          </div>
        </SectionCard>
      </LoadingBlock>
    </section>
  </div>
</template>
