<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import LeadStoryCard from '../components/news/LeadStoryCard.vue';
import NewsCard from '../components/news/NewsCard.vue';
import StoryStrip from '../components/news/StoryStrip.vue';
import { useNewsStore } from '../stores/newsStore';
import type { Market, SentimentLabel } from '../types/api';
import { groupEditorialStories } from '../utils/newsEditorial';

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
const editorialGroup = computed(() => groupEditorialStories(newsStore.items, newsStore.detailMap, { supportingCount: 3 }));

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
        <p class="page-subtitle">Signal Desk：先看最该读的主信号，再顺着次级线索和新闻流快速扫描。</p>
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
          <h2>Primary Signal</h2>
          <p class="edition-copy">混合考虑主题热度、上下文完整度和发布时间，让首页优先暴露最值得跟踪的主信号。</p>
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
        <div class="editorial-flow">
          <LeadStoryCard
            v-if="editorialGroup.lead"
            :entry="editorialGroup.lead"
            @open="openStory"
          />

          <StoryStrip
            v-if="editorialGroup.supporting.length"
            title="Signal Queue"
            :stories="editorialGroup.supporting"
            @open="openStory"
          />

          <SectionCard
            eyebrow="Live Flow"
            title="News Stream"
            subtitle="保留更多新闻，但改成更适合快速扫读和连续跟踪的终端式流卡片。"
            compact
          >
            <div class="story-stream">
              <NewsCard
                v-for="entry in editorialGroup.stream"
                :key="entry.item.id"
                :entry="entry"
                variant="stream"
                @open="openStory"
              />
            </div>
          </SectionCard>
        </div>
      </LoadingBlock>
    </section>
  </div>
</template>

<style scoped>
.page {
  display: grid;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.edition-surface {
  display: grid;
  gap: 20px;
  padding: 22px;
  border-radius: 24px;
}

.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.02);
}

.filters select,
.filters input {
  min-width: 138px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(7, 11, 17, 0.86);
  padding: 10px 12px;
  color: var(--text);
}

.filters input {
  min-width: 240px;
}

.edition-head {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
}

.edition-label {
  margin: 0 0 8px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--system);
}

.edition-head h2 {
  margin: 0;
  font-size: 32px;
  letter-spacing: -0.04em;
}

.edition-copy {
  max-width: 60ch;
  margin: 10px 0 0;
  color: var(--muted);
  line-height: 1.7;
}

.editorial-flow {
  display: grid;
  gap: 18px;
}

.story-stream {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 1320px) {
  .story-stream {
    grid-template-columns: 1fr;
  }
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
