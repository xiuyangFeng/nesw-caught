<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import { useTopicStore } from '../stores/topicStore';
import { sentimentText } from '../utils/format';
import { compareNewsTimestamps, formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../utils/time';

const route = useRoute();
const router = useRouter();
const topicStore = useTopicStore();
const viewMode = ref<'grouped' | 'timeline'>('grouped');
const sentimentFilter = ref<'all' | 'positive' | 'negative' | 'neutral'>('all');
const symbolFilter = ref<string>('all');
const keywordQuery = ref('');
const originalOnly = ref(false);

const topicId = computed(() => Number(route.params.id));
const detail = computed(() => topicStore.detailMap[topicId.value] ?? null);
const sortedSources = computed(() =>
  [...(detail.value?.sources ?? [])]
    .filter((item) => {
      const sentimentOk = sentimentFilter.value === 'all' || item.sentiment_label === sentimentFilter.value;
      const symbolOk =
        symbolFilter.value === 'all' ||
        detail.value?.related_symbols.includes(symbolFilter.value) === false ||
        item.summary?.includes(symbolFilter.value) ||
        item.title.includes(symbolFilter.value);
      const keyword = keywordQuery.value.trim().toLowerCase();
      const keywordOk =
        !keyword ||
        `${item.title} ${item.summary ?? ''} ${item.source_name}`.toLowerCase().includes(keyword);
      const originalOk = !originalOnly.value || Boolean(item.canonical_url);
      return sentimentOk && Boolean(symbolOk) && keywordOk && originalOk;
    })
    .sort((left, right) => compareNewsTimestamps(left, right)),
);
const availableSymbols = computed(() => detail.value?.related_symbols ?? []);
const sourceGroups = computed(() => {
  const groups = new Map<
    string,
    {
      sourceName: string;
      count: number;
      items: typeof sortedSources.value;
      latestPublishedAt: string;
      firstPublishedAt: string;
      sentimentCounts: Record<string, number>;
    }
  >();

  for (const item of sortedSources.value) {
    const existing = groups.get(item.source_name);
    if (existing) {
      existing.count += 1;
      existing.items.push(item);
      const itemTimestamp = getNewsDisplayTimestamp(item) ?? '';
      if (compareNewsTimestamps({ published_at: existing.latestPublishedAt }, { published_at: itemTimestamp }) > 0) {
        existing.latestPublishedAt = itemTimestamp;
      }
      if (compareNewsTimestamps({ published_at: itemTimestamp }, { published_at: existing.firstPublishedAt }) > 0) {
        existing.firstPublishedAt = itemTimestamp;
      }
      existing.sentimentCounts[item.sentiment_label] = (existing.sentimentCounts[item.sentiment_label] ?? 0) + 1;
    } else {
      const timestamp = getNewsDisplayTimestamp(item) ?? '';
      groups.set(item.source_name, {
        sourceName: item.source_name,
        count: 1,
        items: [item],
        latestPublishedAt: timestamp,
        firstPublishedAt: timestamp,
        sentimentCounts: { [item.sentiment_label]: 1 },
      });
    }
  }

  return [...groups.values()].sort((left, right) =>
    compareNewsTimestamps({ published_at: left.latestPublishedAt }, { published_at: right.latestPublishedAt }),
  );
});
const sourceStats = computed(() =>
  sourceGroups.value.map((group) => ({
    sourceName: group.sourceName,
    count: group.count,
  })),
);

function sentimentSummary(sentimentCounts: Record<string, number>) {
  return Object.entries(sentimentCounts)
    .sort((left, right) => right[1] - left[1])
    .map(([label, count]) => `${sentimentText(label as never)} ${count}`)
    .join(' · ');
}

function openNews(newsId: number) {
  router.push({ name: 'news-detail', params: { id: newsId } });
}

function isHighlighted(item: { title: string; summary: string | null }) {
  return symbolFilter.value !== 'all' && (`${item.title} ${item.summary ?? ''}`).includes(symbolFilter.value);
}

onMounted(async () => {
  if (!detail.value) {
    await topicStore.loadDetail(topicId.value);
  }
});
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">Topic Detail</h1>
        <p class="page-subtitle">主题聚合下的全部来源、关联股票和时间线都在这里展开。</p>
      </div>
      <StaleBadge :stale="topicStore.stale" label="主题详情" />
    </header>

    <LoadingBlock :loading="topicStore.detailLoading" :empty="!detail" empty-text="主题不存在或尚未完成聚合">
      <div v-if="detail" class="detail-layout">
        <SectionCard :title="detail.topic_title" :subtitle="detail.topic_summary ?? '主题摘要待补充'">
          <div class="topic-meta">
            <span class="pill" :class="detail.sentiment_label">{{ sentimentText(detail.sentiment_label) }}</span>
            <span>{{ detail.news_count }} 条来源</span>
            <span>{{ sourceGroups.length }} 个信息源</span>
            <span>{{ detail.related_symbols.join(' · ') || '无关联股票' }}</span>
            <span>{{ formatMarketTime(detail.last_seen_at, detail.market) }} {{ getMarketTimezoneLabel(detail.market) }}</span>
          </div>
          <div class="keyword-list">
            <span v-for="keyword in detail.keywords" :key="keyword" class="pill neutral">{{ keyword }}</span>
          </div>
          <div class="source-stats">
            <span v-for="stat in sourceStats" :key="stat.sourceName" class="stat-chip">
              {{ stat.sourceName }} · {{ stat.count }} 条
            </span>
          </div>
        </SectionCard>

        <SectionCard title="全部信息来源" subtitle="按来源分组，组内按时间倒序，支持原文直达和详情下钻">
          <template #actions>
            <div class="toolbar">
              <div class="filters">
                <select v-model="sentimentFilter">
                  <option value="all">全部情绪</option>
                  <option value="positive">偏利好</option>
                  <option value="negative">偏利空</option>
                  <option value="neutral">中性</option>
                </select>
                <select v-model="symbolFilter">
                  <option value="all">全部股票</option>
                  <option v-for="symbol in availableSymbols" :key="symbol" :value="symbol">{{ symbol }}</option>
                </select>
                <input v-model.trim="keywordQuery" type="search" placeholder="按关键词、来源或摘要过滤" />
                <label class="toggle-filter">
                  <input v-model="originalOnly" type="checkbox" />
                  <span>只看带原文链接</span>
                </label>
              </div>
              <button
                class="switch-button"
                :data-active="viewMode === 'grouped'"
                type="button"
                @click="viewMode = 'grouped'"
              >
                来源分组
              </button>
              <button
                class="switch-button"
                :data-active="viewMode === 'timeline'"
                type="button"
                @click="viewMode = 'timeline'"
              >
                时间线
              </button>
            </div>
          </template>

          <div v-if="viewMode === 'grouped'" class="source-group-list">
            <section v-for="group in sourceGroups" :key="group.sourceName" class="source-group">
              <header class="group-header">
                <div>
                  <strong>{{ group.sourceName }}</strong>
                  <span class="group-count">{{ group.count }} 条来源</span>
                </div>
                <div class="group-time">
                  <span>
                    首条：{{ formatMarketTime(group.firstPublishedAt, detail.market) }}
                    {{ getMarketTimezoneLabel(detail.market) }}
                  </span>
                  <span>
                    最新：{{ formatMarketTime(group.latestPublishedAt, detail.market) }}
                    {{ getMarketTimezoneLabel(detail.market) }}
                  </span>
                </div>
              </header>
              <div class="group-summary">
                <span>{{ sentimentSummary(group.sentimentCounts) }}</span>
              </div>

              <div class="source-list">
                <article
                  v-for="item in group.items"
                  :key="item.id"
                  class="source-card"
                  :data-highlighted="isHighlighted(item)"
                  role="button"
                  tabindex="0"
                  @click="openNews(item.id)"
                  @keydown.enter="openNews(item.id)"
                >
                  <div class="source-head">
                    <span class="pill" :class="item.sentiment_label">{{ sentimentText(item.sentiment_label) }}</span>
                    <span>{{ formatMarketTime(getNewsDisplayTimestamp(item), item.market) }} {{ getMarketTimezoneLabel(item.market) }}</span>
                  </div>
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.summary ?? '摘要待补充' }}</p>
                  <div class="source-actions">
                    <button class="detail-button" type="button" @click.stop="openNews(item.id)">查看详情</button>
                    <a
                      v-if="item.canonical_url"
                      class="origin-link"
                      :href="item.canonical_url"
                      target="_blank"
                      rel="noreferrer"
                      @click.stop
                    >
                      原文直达
                    </a>
                  </div>
                </article>
              </div>
            </section>
          </div>

          <div v-else class="timeline-list">
            <article
              v-for="item in sortedSources"
              :key="item.id"
              class="timeline-card"
              :data-highlighted="isHighlighted(item)"
              role="button"
              tabindex="0"
              @click="openNews(item.id)"
              @keydown.enter="openNews(item.id)"
            >
              <div class="timeline-line" />
              <div class="timeline-content">
                <div class="source-head">
                  <span class="pill" :class="item.sentiment_label">{{ sentimentText(item.sentiment_label) }}</span>
                  <span>{{ item.source_name }}</span>
                  <span>{{ formatMarketTime(getNewsDisplayTimestamp(item), item.market) }} {{ getMarketTimezoneLabel(item.market) }}</span>
                </div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.summary ?? '摘要待补充' }}</p>
                <div class="source-actions">
                  <button class="detail-button" type="button" @click.stop="openNews(item.id)">查看详情</button>
                  <a
                    v-if="item.canonical_url"
                    class="origin-link"
                    :href="item.canonical_url"
                    target="_blank"
                    rel="noreferrer"
                    @click.stop
                  >
                    原文直达
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
.page {
  display: grid;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.detail-layout {
  display: grid;
  gap: 16px;
}

.topic-meta,
.keyword-list,
.source-head {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
}

.keyword-list {
  margin-top: 16px;
}

.source-stats {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.stat-chip {
  border-radius: 999px;
  padding: 8px 12px;
  background: rgba(83, 194, 255, 0.1);
  color: var(--system);
  font-size: 12px;
  font-weight: 600;
}

.source-group-list,
.source-list {
  display: grid;
  gap: 12px;
}

.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filters select {
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--field-bg);
  padding: 8px 12px;
  font: inherit;
  color: var(--text);
}

.filters input[type='search'] {
  min-width: 220px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--field-bg);
  padding: 8px 12px;
  font: inherit;
  color: var(--text);
}

.toggle-filter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--field-bg);
  color: var(--text-faint);
  font-size: 13px;
}

.switch-button {
  border: none;
  border-radius: 999px;
  padding: 8px 12px;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  color: var(--system);
  background: transparent;
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, background-color 160ms ease;
}

.toolbar .switch-button {
  background: rgba(83, 194, 255, 0.08);
}

.switch-button:hover {
  transform: translateY(-1px);
}

.switch-button[data-active='true'] {
  color: white;
  background: linear-gradient(135deg, #1768c2, #3aa9f5);
  box-shadow: 0 10px 22px rgba(58, 169, 245, 0.2);
}

.source-group {
  display: grid;
  gap: 12px;
  border-radius: 20px;
  padding: 16px;
  background: var(--panel-soft);
  border: 1px solid var(--border);
}

.group-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.group-header strong,
.group-count,
.group-time {
  display: block;
}

.group-count,
.group-time {
  color: var(--muted);
  font-size: 12px;
}

.group-time {
  display: grid;
  gap: 4px;
  text-align: right;
}

.group-summary {
  color: var(--muted);
  font-size: 13px;
}

.source-card {
  border-radius: 18px;
  padding: 16px;
  background: var(--panel-stronger);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
}

.source-card:hover,
.timeline-card:hover {
  border-color: rgba(125, 211, 252, 0.24);
  transform: translateY(-1px);
}

.source-card[data-highlighted='true'],
.timeline-card[data-highlighted='true'] {
  border-color: rgba(83, 194, 255, 0.42);
  box-shadow: 0 10px 24px rgba(83, 194, 255, 0.12);
}

.source-card p,
.source-time {
  color: var(--text-soft);
}

.source-head {
  margin-bottom: 10px;
  font-size: 12px;
}

.source-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
  align-items: center;
  flex-wrap: wrap;
}

.timeline-list {
  display: grid;
  gap: 12px;
}

.timeline-card {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 14px;
  border-radius: 18px;
  padding: 16px;
  background: var(--panel-stronger);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
}

.timeline-line {
  width: 14px;
  border-radius: 999px;
  background: linear-gradient(180deg, #3aa9f5, rgba(83, 194, 255, 0.12));
}

.timeline-content {
  display: grid;
  gap: 10px;
}

.detail-button,
.origin-link {
  border-radius: 999px;
  padding: 8px 12px;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
}

.detail-button {
  border: none;
  color: white;
  background: linear-gradient(135deg, #1768c2, #3aa9f5);
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease;
}

.detail-button:hover,
.origin-link:hover {
  transform: translateY(-1px);
}

.origin-link {
  color: var(--system);
  background: rgba(83, 194, 255, 0.08);
}
</style>
