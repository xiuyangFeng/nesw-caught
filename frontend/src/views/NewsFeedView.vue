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

const sourceOptions = computed(() => [...new Set(newsStore.items.map((item) => item.source_name))]);
const selectedSource = ref('');
const hydratingIds = new Set<number>();
const orderedEntries = computed<EditorialStoryEntry[]>(() =>
  newsStore.items.map((item) => ({
    item,
    detail: newsStore.detailMap[item.id] ?? null,
    score: 0,
  })),
);

async function hydrateEditorialDetails() {
  const idsToLoad = newsStore.items
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
    await newsStore.loadNews({
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
  if (!newsStore.items.length) {
    await newsStore.loadNews({ limit: 300 });
  }
  await hydrateEditorialDetails();
});
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">News Feed</h1>
        <p class="page-subtitle">Signal Desk：按当前新闻顺序直接平铺，统一用紧凑横向卡片快速扫读。</p>
      </div>
      <StaleBadge :stale="newsStore.stale" label="新闻列表" />
    </header>

    <StatusBanner
      kicker="System"
      :title="newsStore.usingMock ? '已启用 mock 兼容层' : '历史数据来自 REST 接口'"
      :tone="newsStore.usingMock ? 'warning' : 'default'"
      detail="当详情接口或主题接口缺失时，页面保留空状态和降级文案，不臆造字段。"
    />

    <section class="edition-surface surface">
      <div class="edition-head">
        <div>
          <p class="edition-label">Signal Desk</p>
          <h2>News Stream</h2>
          <p class="edition-copy">不再放大单条新闻，所有条目按当前顺序进入同一种横向信息卡列表。</p>
        </div>
        <div class="filters" data-role="filter-bar">
          <select v-model="filters.market">
            <option value="">全部市场</option>
            <option value="cn">A股/国内</option>
            <option value="hk">港股</option>
            <option value="us">美股</option>
          </select>
          <select v-model="filters.sentiment_label">
            <option value="">全部情绪</option>
            <option value="positive">偏利好</option>
            <option value="negative">偏利空</option>
            <option value="neutral">中性</option>
          </select>
          <select v-model="selectedSource">
            <option value="">全部来源</option>
            <option v-for="source in sourceOptions" :key="source" :value="source">{{ source }}</option>
          </select>
          <input v-model="filters.q" type="search" placeholder="搜索标题或摘要" />
        </div>
      </div>

      <LoadingBlock :loading="newsStore.loading" :empty="newsStore.items.length === 0">
        <SectionCard
          eyebrow="Live Flow"
          title="News Stream"
          subtitle="统一横向卡片，保持当前顺序，方便连续扫读和快速点进详情。"
          compact
        >
          <div class="story-stream" data-role="news-stream-list">
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

<style scoped>
.page {
  display: grid;
  gap: 14px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.edition-surface {
  display: grid;
  gap: 18px;
  padding: 20px;
  border-radius: 22px;
}

.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.015);
}

.filters select,
.filters input {
  min-width: 138px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(6, 11, 19, 0.92);
  padding: 10px 12px;
  color: var(--text);
}

.filters input {
  min-width: 240px;
}

.edition-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.edition-label {
  margin: 0 0 8px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--accent);
}

.edition-head h2 {
  margin: 0;
  font-size: 28px;
  letter-spacing: -0.035em;
}

.edition-copy {
  max-width: 60ch;
  margin: 8px 0 0;
  color: var(--muted);
  line-height: 1.65;
}

.story-stream {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

@media (max-width: 1120px) {
  .edition-head {
    flex-direction: column;
  }

  .filters input,
  .filters select {
    min-width: 0;
  }
}
</style>
