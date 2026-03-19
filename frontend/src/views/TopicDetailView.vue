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
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h1 class="page-title">Topic Detail</h1>
        <p class="page-subtitle">主题聚合下的全部来源、关联股票和时间线都在这里展开。</p>
      </div>
      <StaleBadge :stale="topicStore.stale" label="主题详情" />
    </header>

    <LoadingBlock :loading="topicStore.detailLoading" :empty="!detail" empty-text="主题不存在或尚未完成聚合">
      <div v-if="detail" class="grid gap-4" data-role="topic-detail-layout">
        <SectionCard :title="detail.topic_title" :subtitle="detail.topic_summary ?? '主题摘要待补充'">
          <div class="flex flex-wrap gap-2 text-muted">
            <span class="pill" :class="detail.sentiment_label">{{ sentimentText(detail.sentiment_label) }}</span>
            <span>{{ detail.news_count }} 条来源</span>
            <span>{{ sourceGroups.length }} 个信息源</span>
            <span>{{ detail.related_symbols.join(' · ') || '无关联股票' }}</span>
            <span>{{ formatMarketTime(detail.last_seen_at, detail.market) }} {{ getMarketTimezoneLabel(detail.market) }}</span>
          </div>
          <div class="mt-4 flex flex-wrap gap-2">
            <span v-for="keyword in detail.keywords" :key="keyword" class="pill neutral">{{ keyword }}</span>
          </div>
          <div class="mt-4 flex flex-wrap gap-2">
            <span
              v-for="stat in sourceStats"
              :key="stat.sourceName"
              class="rounded-full bg-system/10 px-3 py-2 text-xs font-semibold text-system"
            >
              {{ stat.sourceName }} · {{ stat.count }} 条
            </span>
          </div>
        </SectionCard>

        <SectionCard title="全部信息来源" subtitle="按来源分组，组内按时间倒序，支持原文直达和详情下钻">
          <template #actions>
            <div class="flex flex-wrap items-center gap-2" data-role="topic-toolbar">
              <div class="flex flex-wrap gap-2">
                <select v-model="sentimentFilter" class="rounded-full border border-border bg-field px-3 py-2 text-text">
                  <option value="all">全部情绪</option>
                  <option value="positive">偏利好</option>
                  <option value="negative">偏利空</option>
                  <option value="neutral">中性</option>
                </select>
                <select v-model="symbolFilter" class="rounded-full border border-border bg-field px-3 py-2 text-text">
                  <option value="all">全部股票</option>
                  <option v-for="symbol in availableSymbols" :key="symbol" :value="symbol">{{ symbol }}</option>
                </select>
                <input
                  v-model.trim="keywordQuery"
                  class="min-w-[220px] rounded-full border border-border bg-field px-3 py-2 text-text"
                  type="search"
                  placeholder="按关键词、来源或摘要过滤"
                />
                <label class="inline-flex items-center gap-1.5 rounded-full border border-border bg-field px-3 py-2 text-[13px] text-text-faint">
                  <input v-model="originalOnly" type="checkbox" />
                  <span>只看带原文链接</span>
                </label>
              </div>
              <button
                class="rounded-full px-3 py-2 text-xs font-semibold"
                :class="viewMode === 'grouped' ? 'bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] text-white' : 'bg-system/10 text-system'"
                type="button"
                @click="viewMode = 'grouped'"
              >
                来源分组
              </button>
              <button
                class="rounded-full px-3 py-2 text-xs font-semibold"
                :class="viewMode === 'timeline' ? 'bg-[linear-gradient(135deg,#1768c2,#3aa9f5)] text-white' : 'bg-system/10 text-system'"
                type="button"
                @click="viewMode = 'timeline'"
              >
                时间线
              </button>
            </div>
          </template>

          <div v-if="viewMode === 'grouped'" class="grid gap-3" data-role="topic-group-list">
            <section
              v-for="group in sourceGroups"
              :key="group.sourceName"
              class="grid gap-3 rounded-[20px] border border-border bg-panel-soft p-4"
            >
              <header class="flex flex-col gap-2 xl:flex-row xl:items-start xl:justify-between">
                <div>
                  <strong>{{ group.sourceName }}</strong>
                  <span class="block text-xs text-muted">{{ group.count }} 条来源</span>
                </div>
                <div class="grid gap-1 text-right text-xs text-muted">
                  <span>首条：{{ formatMarketTime(group.firstPublishedAt, detail.market) }} {{ getMarketTimezoneLabel(detail.market) }}</span>
                  <span>最新：{{ formatMarketTime(group.latestPublishedAt, detail.market) }} {{ getMarketTimezoneLabel(detail.market) }}</span>
                </div>
              </header>
              <div class="text-[13px] text-muted">{{ sentimentSummary(group.sentimentCounts) }}</div>
              <div class="grid gap-3">
                <article
                  v-for="item in group.items"
                  :key="item.id"
                  class="grid gap-3 rounded-[18px] border bg-panel-stronger p-4 transition duration-150 ease-out hover:-translate-y-px hover:border-system/25"
                  :class="isHighlighted(item) ? 'border-system/40 shadow-[0_10px_24px_rgba(83,194,255,0.12)]' : 'border-border'"
                  data-role="topic-source-card"
                  role="button"
                  tabindex="0"
                  @click="openNews(item.id)"
                  @keydown.enter="openNews(item.id)"
                >
                  <div class="mb-1 flex flex-wrap gap-2 text-xs text-muted">
                    <span class="pill" :class="item.sentiment_label">{{ sentimentText(item.sentiment_label) }}</span>
                    <span>{{ formatMarketTime(getNewsDisplayTimestamp(item), item.market) }} {{ getMarketTimezoneLabel(item.market) }}</span>
                  </div>
                  <strong>{{ item.title }}</strong>
                  <p class="text-text-soft">{{ item.summary ?? '摘要待补充' }}</p>
                  <div class="flex flex-wrap items-center gap-2.5">
                    <button class="rounded-full border border-border px-3 py-2 text-xs font-semibold text-text" type="button" @click.stop="openNews(item.id)">
                      查看详情
                    </button>
                    <a
                      v-if="item.canonical_url"
                      class="rounded-full border border-border px-3 py-2 text-xs font-semibold text-text no-underline"
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

          <div v-else class="grid gap-3">
            <article
              v-for="item in sortedSources"
              :key="item.id"
              class="grid grid-cols-[14px_minmax(0,1fr)] gap-3.5 rounded-[18px] border bg-panel-stronger p-4 transition duration-150 ease-out hover:-translate-y-px hover:border-system/25"
              :class="isHighlighted(item) ? 'border-system/40 shadow-[0_10px_24px_rgba(83,194,255,0.12)]' : 'border-border'"
              role="button"
              tabindex="0"
              @click="openNews(item.id)"
              @keydown.enter="openNews(item.id)"
            >
              <div class="rounded-full bg-[linear-gradient(180deg,#3aa9f5,rgba(83,194,255,0.12))]" />
              <div class="grid gap-2.5">
                <div class="flex flex-wrap gap-2 text-xs text-muted">
                  <span class="pill" :class="item.sentiment_label">{{ sentimentText(item.sentiment_label) }}</span>
                  <span>{{ item.source_name }}</span>
                  <span>{{ formatMarketTime(getNewsDisplayTimestamp(item), item.market) }} {{ getMarketTimezoneLabel(item.market) }}</span>
                </div>
                <strong>{{ item.title }}</strong>
                <p class="text-text-soft">{{ item.summary ?? '摘要待补充' }}</p>
                <div class="flex flex-wrap items-center gap-2.5">
                  <button class="rounded-full border border-border px-3 py-2 text-xs font-semibold text-text" type="button" @click.stop="openNews(item.id)">
                    查看详情
                  </button>
                  <a
                    v-if="item.canonical_url"
                    class="rounded-full border border-border px-3 py-2 text-xs font-semibold text-text no-underline"
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
