<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import NewsVirtualList from '../components/news/NewsVirtualList.vue';
import { useNewsStore } from '../stores/newsStore';
import type { Market, SentimentLabel } from '../types/api';
import { formatMarketTime, getMarketTimezoneLabel } from '../utils/time';

const newsStore = useNewsStore();
const router = useRouter();
const activeId = ref<number | null>(null);
const filters = reactive<{
  market: Market | '';
  sentiment_label: SentimentLabel | '';
  q: string;
}>({
  market: '',
  sentiment_label: '',
  q: '',
});

const activeDetail = computed(() => (activeId.value ? newsStore.detailMap[activeId.value] ?? null : null));
const sourceOptions = computed(() => [...new Set(newsStore.items.map((item) => item.source_name))]);
const selectedSource = ref('');

watch(
  () => ({ ...filters, source_name: selectedSource.value }),
  async () => {
    await newsStore.loadNews({
      ...filters,
      source_name: selectedSource.value,
      limit: 300,
    });
  },
);

async function selectNews(id: number) {
  activeId.value = id;
  if (!newsStore.detailMap[id]) {
    await newsStore.loadDetail(id);
  }
}

function openTopic(topicId: number) {
  router.push({ name: 'topic-detail', params: { id: topicId } });
}

onMounted(async () => {
  if (!newsStore.items.length) {
    await newsStore.loadNews({ limit: 300 });
  }
  if (newsStore.items.length > 0 && !activeId.value) {
    await selectNews(newsStore.items[0].id);
  }
});
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">News Feed</h1>
        <p class="page-subtitle">从一开始按长列表方案搭建，筛选、详情、股票关联和主题入口同屏可见。</p>
      </div>
      <StaleBadge :stale="newsStore.stale" label="新闻列表" />
    </header>

    <StatusBanner
      :title="newsStore.usingMock ? '已启用 mock 兼容层' : '历史数据来自 REST 接口'"
      :tone="newsStore.usingMock ? 'warning' : 'default'"
      detail="当详情接口或主题接口缺失时，页面保留空状态和降级文案，不臆造字段。"
    />

    <section class="feed-layout">
      <SectionCard title="筛选与列表" subtitle="虚拟列表窗口，后续数据增长时不需要重构">
        <template #actions>
          <div class="filters">
            <select v-model="filters.market">
              <option value="">全部市场</option>
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
        </template>
        <LoadingBlock :loading="newsStore.loading" :empty="newsStore.items.length === 0">
          <NewsVirtualList :items="newsStore.items" :detail-map="newsStore.detailMap" :active-id="activeId" @select="selectNews" />
        </LoadingBlock>
      </SectionCard>

      <SectionCard title="详情与关联" subtitle="正文提取、股票命中、主题聚合和时间展示按市场时区区分">
        <LoadingBlock :loading="newsStore.detailLoading" :empty="!activeDetail" empty-text="选择一条新闻查看详情">
          <div v-if="activeDetail" class="detail-panel">
            <div class="detail-head">
              <span class="pill" :class="activeDetail.sentiment_label">{{ activeDetail.sentiment_label }}</span>
              <strong>{{ activeDetail.title }}</strong>
            </div>
            <p class="detail-summary">{{ activeDetail.summary }}</p>
            <div class="detail-meta">
              <span>{{ activeDetail.source_name }}</span>
              <span>
                {{ formatMarketTime(activeDetail.published_at, activeDetail.market) }}
                {{ getMarketTimezoneLabel(activeDetail.market) }}
              </span>
              <a v-if="activeDetail.canonical_url" :href="activeDetail.canonical_url" target="_blank" rel="noreferrer">原文</a>
            </div>

            <div class="detail-block">
              <h3>正文提取状态</h3>
              <p>
                {{ activeDetail.article?.extract_status ?? 'not_requested' }}
                <span v-if="activeDetail.article?.extract_error"> · {{ activeDetail.article.extract_error }}</span>
              </p>
              <p>{{ activeDetail.article?.content_text ?? '正文缺失时仍保留新闻和主题入口。' }}</p>
            </div>

            <div class="detail-block">
              <h3>股票关联</h3>
              <div class="mention-list">
                <span v-for="mention in activeDetail.mentions" :key="`${mention.symbol}-${mention.mention_type}`" class="pill neutral">
                  {{ mention.symbol }} · {{ Math.round(mention.confidence * 100) }}%
                </span>
                <span v-if="activeDetail.mentions.length === 0">暂无股票关联</span>
              </div>
            </div>

            <div class="detail-block">
              <h3>主题聚合</h3>
              <button v-if="activeDetail.topic" class="topic-button" type="button" @click="openTopic(activeDetail.topic.id)">
                {{ activeDetail.topic.topic_title }} · 热度 {{ activeDetail.topic.importance_score.toFixed(2) }}
              </button>
              <p v-else>尚未聚合到主题。</p>
            </div>
          </div>
        </LoadingBlock>
      </SectionCard>
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
}

.feed-layout {
  display: grid;
  grid-template-columns: 1.35fr 0.8fr;
  gap: 16px;
  align-items: start;
}

.filters {
  display: flex;
  gap: 8px;
}

.filters select,
.filters input {
  border-radius: 12px;
  border: 1px solid var(--border);
  background: #fffdf8;
  padding: 10px 12px;
}

.detail-panel {
  display: grid;
  gap: 16px;
}

.detail-head {
  display: grid;
  gap: 10px;
}

.detail-head strong {
  font-size: 22px;
}

.detail-summary,
.detail-meta,
.detail-block p {
  color: var(--muted);
}

.detail-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.detail-block {
  border-radius: 18px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid var(--border);
}

.detail-block h3 {
  margin: 0 0 10px;
}

.mention-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.topic-button {
  border: none;
  border-radius: 999px;
  padding: 10px 14px;
  font: inherit;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #1453a3, #1e7acb);
  cursor: pointer;
}
</style>
