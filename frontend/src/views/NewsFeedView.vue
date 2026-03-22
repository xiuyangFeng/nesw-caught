<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import NewsCard from '../components/news/NewsCard.vue';
import { useNewsStore } from '../stores/newsStore';
import type { Market, SentimentLabel } from '../types/api';
import type { EditorialStoryEntry } from '../utils/newsEditorial';

const newsStore = useNewsStore();
const router = useRouter();
const filters = reactive<{
  market: Market | '';
  sentiment_label: SentimentLabel | '';
  q: string;
}>({
  market: '',
  sentiment_label: '',
  q: '',
});

const sourceOptions = computed(() => [...new Set(newsStore.feedItems.map((item) => item.source_name))]);
const selectedSource = ref('');
const hydratingIds = new Set<number>();
const orderedEntries = computed<EditorialStoryEntry[]>(() =>
  newsStore.feedItems.map((item) => ({
    item,
    detail: newsStore.detailMap[item.id] ?? null,
    score: 0,
  })),
);

async function hydrateEditorialDetails() {
  const idsToLoad = newsStore.feedItems
    .slice(0, 8)
    .map((item) => item.id)
    .filter((id) => !newsStore.detailMap[id] && !hydratingIds.has(id));

  if (!idsToLoad.length) {
    return;
  }

  idsToLoad.forEach((id) => hydratingIds.add(id));
  await Promise.all(
    idsToLoad.map(async (id) => {
      try {
        await newsStore.loadDetail(id);
      } finally {
        hydratingIds.delete(id);
      }
    }),
  );
}

watch(
  () => ({ ...filters, source_name: selectedSource.value }),
  async () => {
    await newsStore.loadFeedNews({
      ...filters,
      source_name: selectedSource.value,
      limit: 300,
    });
    await hydrateEditorialDetails();
  },
);

function openStory(id: number) {
  router.push({ name: 'news-detail', params: { id } });
}

onMounted(async () => {
  if (!newsStore.feedItems.length) {
    await newsStore.loadFeedNews({ limit: 300 });
  }
  await hydrateEditorialDetails();
});
</script>

<template>
  <div class="grid gap-[14px]">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h1 class="page-title">News Feed</h1>
        <p class="page-subtitle">Signal Desk：按当前新闻顺序直接平铺，统一用紧凑横向卡片快速扫读。</p>
      </div>
      <StaleBadge :stale="newsStore.feedStale" label="新闻列表" />
    </header>

    <StatusBanner
      kicker="System"
      :title="newsStore.usingMock ? '已启用 mock 兼容层' : '历史数据来自 REST 接口'"
      :tone="newsStore.usingMock ? 'warning' : 'default'"
      detail="当详情接口或主题接口缺失时，页面保留空状态和降级文案，不臆造字段。"
    />

    <section class="surface grid gap-[18px] rounded-[22px] p-5" data-role="news-feed-shell">
      <div class="flex flex-col items-start justify-between gap-4 xl:flex-row">
        <div>
          <p class="mb-2 text-[11px] uppercase tracking-[0.2em] text-[#ffb77d]">Control Station</p>
          <p class="mb-2 text-[11px] uppercase tracking-[0.18em] text-accent">Signal Desk</p>
          <h2 class="m-0 text-[28px] tracking-[-0.035em] text-text">News Stream</h2>
          <p class="mt-2 max-w-[60ch] leading-[1.65] text-muted">
            不再放大单条新闻，所有条目按当前顺序进入同一种横向信息卡列表。
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

      <LoadingBlock :loading="newsStore.feedLoading" :empty="newsStore.feedItems.length === 0">
        <SectionCard
          eyebrow="Live Flow"
          title="News Stream"
          subtitle="统一横向卡片，保持当前顺序，方便连续扫读和快速点进详情。"
          compact
          data-role="news-stream-shell"
        >
          <div class="grid grid-cols-1 gap-[14px]" data-role="news-stream-list">
            <NewsCard
              v-for="entry in orderedEntries"
              :key="entry.item.id"
              :entry="entry"
              variant="stream"
              @open="openStory"
            />
          </div>
        </SectionCard>
      </LoadingBlock>
    </section>
  </div>
</template>
