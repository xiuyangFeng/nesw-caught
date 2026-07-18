<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import NewsCard from '../components/news/NewsCard.vue';
import NewsVirtualList from '../components/news/NewsVirtualList.vue';
import EventCapsuleStrip from '../components/news/EventCapsuleStrip.vue';
import TopicChipsRow from '../components/news/TopicChipsRow.vue';
import NewsDetailDrawer from '../components/news/NewsDetailDrawer.vue';
import { useFeedKeyboard } from '../composables/useFeedKeyboard';
import { partitionFoldableStream } from '../utils/newsFolding';
import { markNewsRead, useReadNewsIds } from '../utils/readNews';
import { useConnectionStore } from '../stores/connectionStore';
import { useNewsStore } from '../stores/newsStore';
import type { Market, SentimentLabel } from '../types/api';
import type { EditorialStoryEntry } from '../utils/newsEditorial';
import { rankEditorialStories } from '../utils/newsEditorial';

const newsStore = useNewsStore();
const connectionStore = useConnectionStore();
const router = useRouter();
const VIRTUAL_LIST_THRESHOLD = 30;
const FEED_PAGE_SIZE = 50;
const FEED_LAYOUT_STREAM_LIMIT = 100;
const loadMoreSentinelRef = ref<HTMLElement | null>(null);
let loadMoreObserver: IntersectionObserver | null = null;
const filters = reactive<{
  market: Market | '';
  sentiment_label: SentimentLabel | '';
  q: string;
}>({
  market: '',
  sentiment_label: '',
  q: '',
});

// market/sentiment_label 以后端 schema 为准是普通(可空)string,过滤时直接与选中值比较
function matchesFilters(item: { market: string; sentiment_label?: string | null; source_name?: string; title?: string; summary?: string | null }) {
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
const displayedFeedItems = ref<any[]>([...newsStore.feedItems]);
const pendingNewItems = ref<any[]>([]);

watch(() => newsStore.feedItems, (newVal) => {
  if (newsStore.feedLoading || newsStore.feedLoadingMore) {
    displayedFeedItems.value = [...newVal];
    pendingNewItems.value = [];
    return;
  }

  const existingIds = new Set(displayedFeedItems.value.map(item => item.id));
  const added = newVal.filter(item => !existingIds.has(item.id));

  if (added.length > 0) {
    const latestDisplayedTime = displayedFeedItems.value[0]?.published_at 
      ? new Date(displayedFeedItems.value[0].published_at).getTime() 
      : 0;

    const newPending: any[] = [];
    const toImmediatelyInsert: any[] = [];

    added.forEach(item => {
      const itemTime = new Date(item.published_at ?? item.fetched_at).getTime();
      if (itemTime > latestDisplayedTime) {
        newPending.push(item);
      } else {
        toImmediatelyInsert.push(item);
      }
    });

    if (newPending.length > 0) {
      const pendingIds = new Set(pendingNewItems.value.map(x => x.id));
      newPending.forEach(item => {
        if (!pendingIds.has(item.id)) {
          pendingNewItems.value.push(item);
        }
      });
      pendingNewItems.value.sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime());
    }

    if (toImmediatelyInsert.length > 0) {
      displayedFeedItems.value = newVal.filter(item => !pendingNewItems.value.some(p => p.id === item.id));
    }
  } else {
    displayedFeedItems.value = [...newVal];
  }
}, { deep: true, flush: 'sync' });

function applyPendingNews() {
  if (pendingNewItems.value.length === 0) return;
  displayedFeedItems.value = [...pendingNewItems.value, ...displayedFeedItems.value];
  pendingNewItems.value = [];
}

const rankedFeedItems = computed(() =>
  displayedFeedItems.value.map((item) => {
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

const drawerVisible = ref(false);
const selectedNewsId = ref<number | null>(null);
const foldExpanded = ref(false);
const readIds = useReadNewsIds();
const virtualListRef = ref<InstanceType<typeof NewsVirtualList> | null>(null);

const foldedStream = computed(() => partitionFoldableStream(orderedEntries.value));
const displayEntries = computed(() =>
  foldExpanded.value
    ? [...foldedStream.value.visible, ...foldedStream.value.folded]
    : foldedStream.value.visible,
);
const displayIds = computed(() => displayEntries.value.map((entry) => entry.item.id));

const useVirtualScrolling = computed(() => displayEntries.value.length > VIRTUAL_LIST_THRESHOLD);
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

const SEARCH_DEBOUNCE_MS = 300;
let searchDebounceHandle: ReturnType<typeof setTimeout> | null = null;
let feedSearchAbort: AbortController | null = null;
let lastLayoutMarket: string | undefined;
let pendingLayoutReload = false;

async function reloadFeedForFilters(options: { reloadLayout: boolean }) {
  feedSearchAbort?.abort();
  feedSearchAbort = new AbortController();
  const signal = feedSearchAbort.signal;
  const tasks: Promise<unknown>[] = [
    newsStore.loadFeedNews({
      ...filters,
      source_name: selectedSource.value || undefined,
      limit: FEED_PAGE_SIZE,
    }),
  ];
  if (options.reloadLayout) {
    tasks.unshift(
      newsStore.loadFeedLayout({
        market: filters.market || undefined,
        limit_events: 6,
        limit_topics: 6,
        limit_stream: FEED_LAYOUT_STREAM_LIMIT,
      }),
    );
  }
  await Promise.all(tasks);
  if (signal.aborted) {
    return;
  }
  await hydrateEditorialDetails();
}

watch(
  () => ({ ...filters, source_name: selectedSource.value }),
  (next) => {
    const market = next.market || undefined;
    if (market !== lastLayoutMarket) {
      lastLayoutMarket = market;
      pendingLayoutReload = true;
    }
    if (searchDebounceHandle !== null) {
      clearTimeout(searchDebounceHandle);
    }
    searchDebounceHandle = setTimeout(() => {
      searchDebounceHandle = null;
      const reloadLayout = pendingLayoutReload;
      pendingLayoutReload = false;
      void reloadFeedForFilters({ reloadLayout });
    }, SEARCH_DEBOUNCE_MS);
  },
);

function openStory(id: number) {
  markNewsRead(id);
  selectedNewsId.value = id;
  drawerVisible.value = true;
  keyboard.selectedId.value = id;
}

function closeDrawer() {
  drawerVisible.value = false;
  selectedNewsId.value = null;
}

function changeNewsInDrawer(id: number) {
  markNewsRead(id);
  selectedNewsId.value = id;
  keyboard.selectedId.value = id;
}

function openEvent(eventKey: string) {
  router.push({ name: 'event-detail', params: { eventKey } });
}

function openTopic(id: number) {
  router.push({ name: 'topic-detail', params: { id } });
}

function scrollSelectedIntoView(id: number, index: number) {
  if (useVirtualScrolling.value) {
    virtualListRef.value?.scrollToIndex(index);
    return;
  }
  document.querySelector(`[data-news-id="${id}"]`)?.scrollIntoView({ block: 'nearest' });
}

const keyboard = useFeedKeyboard({
  ids: () => displayIds.value,
  isDrawerOpen: () => drawerVisible.value,
  openDrawer: openStory,
  closeDrawer,
  onSelect: scrollSelectedIntoView,
});

onMounted(async () => {
  lastLayoutMarket = filters.market || undefined;
  await Promise.all([
    newsStore.loadFeedLayout({ limit_events: 6, limit_topics: 6, limit_stream: FEED_LAYOUT_STREAM_LIMIT }),
    newsStore.loadFeedNews({ limit: FEED_PAGE_SIZE }),
  ]);
  loadMoreObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        void newsStore.loadMoreFeedNews();
      }
    },
    { rootMargin: '240px 0px' },
  );
  if (loadMoreSentinelRef.value) {
    loadMoreObserver.observe(loadMoreSentinelRef.value);
  }
});

onBeforeUnmount(() => {
  if (searchDebounceHandle !== null) {
    clearTimeout(searchDebounceHandle);
    searchDebounceHandle = null;
  }
  feedSearchAbort?.abort();
  feedSearchAbort = null;
  loadMoreObserver?.disconnect();
  loadMoreObserver = null;
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

watch(loadMoreSentinelRef, (node, previous) => {
  if (previous) {
    loadMoreObserver?.unobserve(previous);
  }
  if (node) {
    loadMoreObserver?.observe(node);
  }
});
</script>

<template>
  <div class="grid gap-[14px]">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h1 class="page-title">Latest Events</h1>
        <p class="page-subtitle">聚焦最新市场事件，按事件优先、证据随后展开。</p>
      </div>
      <StaleBadge :stale="newsStore.feedStale" label="新闻列表" />
    </header>

    <section class="surface grid gap-[18px] rounded-lg p-5" data-role="news-feed-shell">
      <div class="grid gap-3" data-role="news-feed-toolbar">
        <StatusBanner
          kicker="Runtime"
          :title="runtimeBannerTitle"
          :tone="runtimeBannerTone"
          :detail="runtimeBannerDetail"
        />
        <div
          class="flex flex-wrap gap-2 rounded-lg border border-border bg-panel-strong p-2.5"
          data-role="filter-bar"
        >
          <select
            v-model="filters.market"
            class="min-w-[138px] rounded-md border border-border bg-field px-3 py-2.5 text-text"
          >
            <option value="">全部市场</option>
            <option value="cn">A股/国内</option>
            <option value="hk">港股</option>
            <option value="us">美股</option>
          </select>
          <select
            v-model="filters.sentiment_label"
            class="min-w-[138px] rounded-md border border-border bg-field px-3 py-2.5 text-text"
          >
            <option value="">全部情绪</option>
            <option value="positive">偏利好</option>
            <option value="negative">偏利空</option>
            <option value="neutral">中性</option>
          </select>
          <select
            v-model="selectedSource"
            class="min-w-[138px] rounded-md border border-border bg-field px-3 py-2.5 text-text"
          >
            <option value="">全部来源</option>
            <option v-for="source in sourceOptions" :key="source" :value="source">{{ source }}</option>
          </select>
          <input
            v-model="filters.q"
            class="min-w-[240px] rounded-md border border-border bg-field px-3 py-2.5 text-text max-xl:min-w-0"
            type="search"
            placeholder="搜索标题或摘要"
          />
        </div>
      </div>

      <LoadingBlock :loading="newsStore.feedLoading" :empty="!hasVisibleFeedContent" :skeletonType="'news'" :skeletonCount="3">
        <div class="grid gap-2.5" data-role="feed-compact-header">
          <EventCapsuleStrip :events="filteredEvents" @open-event="openEvent" />
          <TopicChipsRow :topics="filteredTopics" @open-topic="openTopic" />
        </div>

        <SectionCard
          eyebrow="Live Flow"
          title="Raw Stream"
          subtitle="保留原始新闻卡片作为证据层，优先级低于事件和主题。"
          compact
          data-role="news-stream-shell"
        >
          <!-- Delta Banner for incremental updates -->
          <transition name="fade-in">
            <div
              v-if="pendingNewItems.length > 0"
              class="mb-3.5 flex items-center justify-between gap-3 rounded-md border border-border bg-[var(--accent-soft)] px-4 py-2.5 text-xs text-accent anim-fade-up transition-colors hover:border-border-strong cursor-pointer select-none"
              @click="applyPendingNews"
            >
              <div class="flex items-center gap-2">
                <span class="inline-block h-1.5 w-1.5 rounded-full bg-accent pulse-dot"></span>
                <span>发现 <strong class="num">{{ pendingNewItems.length }}</strong> 条最新资讯</span>
              </div>
              <span class="font-semibold">点击置入 ↓</span>
            </div>
          </transition>

          <NewsVirtualList
            v-if="useVirtualScrolling"
            ref="virtualListRef"
            :entries="displayEntries"
            :selected-id="keyboard.selectedId.value"
            :read-ids="readIds"
            @open="openStory"
            @visible-ids="visibleStreamIds = $event"
          />
          <div v-else class="grid grid-cols-1 gap-[14px]" data-role="news-stream-list">
            <transition-group name="list-fade-in" tag="div" class="grid grid-cols-1 gap-[14px]">
              <NewsCard
                v-for="entry in displayEntries"
                :key="entry.item.id"
                class="anim-fade-up"
                :entry="entry"
                variant="stream-compact"
                :read="readIds.has(entry.item.id)"
                :selected="entry.item.id === keyboard.selectedId.value"
                @open="openStory"
              />
            </transition-group>
          </div>
          <button
            v-if="foldedStream.folded.length"
            type="button"
            class="fold-toggle"
            data-role="news-fold-toggle"
            @click="foldExpanded = !foldExpanded"
          >
            {{ foldExpanded ? '▴ 收起低优先级' : `▾ 已折叠 ${foldedStream.folded.length} 条低优先级 — 展开` }}
          </button>
          <div
            v-if="newsStore.feedHasMore"
            ref="loadMoreSentinelRef"
            class="py-4 text-center text-sm text-muted"
            data-role="news-stream-load-more"
          >
            {{ newsStore.feedLoadingMore ? '加载更多历史新闻…' : '继续下滑加载更多' }}
          </div>
          <p class="kbd-hint" data-role="feed-kbd-hint">
            <kbd>j</kbd>/<kbd>k</kbd> 上下 · <kbd>Enter</kbd> 阅读 · <kbd>Esc</kbd> 关闭
          </p>
        </SectionCard>
      </LoadingBlock>
    </section>

    <NewsDetailDrawer
      :newsId="selectedNewsId"
      :visible="drawerVisible"
      :filteredNewsIds="displayIds"
      @close="closeDrawer"
      @changeNews="changeNewsInDrawer"
    />
  </div>
</template>

<style scoped>
.fold-toggle {
  width: 100%;
  padding: 10px;
  margin-top: 12px;
  border: 1px dashed var(--border);
  border-radius: var(--r-md);
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  cursor: pointer;
  transition: border-color 140ms ease, color 140ms ease;
}

.fold-toggle:hover {
  border-color: var(--border-strong);
  color: var(--text);
}

.kbd-hint {
  margin: 10px 0 0;
  color: var(--text-faint);
  font-size: 11px;
  text-align: center;
}

.kbd-hint kbd {
  padding: 1px 5px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 10px;
}
</style>
