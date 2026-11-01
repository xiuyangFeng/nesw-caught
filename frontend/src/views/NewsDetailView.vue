<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import NewsAiImpactCard from '../components/news/NewsAiImpactCard.vue';
import { useNewsStore } from '../stores/newsStore';
import { useTopicStore } from '../stores/topicStore';
import { sentimentText } from '../utils/format';
import { getNewsSummary } from '../utils/news';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../utils/time';

const route = useRoute();
const router = useRouter();
const newsStore = useNewsStore();
const topicStore = useTopicStore();

const newsId = computed(() => Number(route.params.id));
const detail = computed(() => newsStore.detailMap[newsId.value] ?? null);
const detailSummary = computed(() => (detail.value ? getNewsSummary(detail.value) : null));
const topicDetail = computed(() => {
  const topicId = detail.value?.topic?.id;
  return topicId ? topicStore.detailMap[topicId] ?? null : null;
});
const currentTopicIndex = computed(() => {
  if (!topicDetail.value) {
    return -1;
  }
  return topicDetail.value.sources.findIndex((item) => item.id === newsId.value);
});
const previousSource = computed(() =>
  currentTopicIndex.value > 0 ? topicDetail.value?.sources[currentTopicIndex.value - 1] ?? null : null,
);
const nextSource = computed(() =>
  currentTopicIndex.value >= 0 && topicDetail.value && currentTopicIndex.value < topicDetail.value.sources.length - 1
    ? topicDetail.value.sources[currentTopicIndex.value + 1]
    : null,
);

function openTopic(topicId: number) {
  router.push({ name: 'topic-detail', params: { id: topicId } });
}

function openSibling(newsIdToOpen: number) {
  router.push({ name: 'news-detail', params: { id: newsIdToOpen } });
}

onMounted(async () => {
  if (!detail.value) {
    await newsStore.loadDetail(newsId.value);
  }
});

watch(
  () => detail.value?.topic?.id,
  async (topicId) => {
    if (topicId && !topicStore.detailMap[topicId]) {
      await topicStore.loadDetail(topicId);
    }
  },
  { immediate: true },
);

watch(
  () => newsId.value,
  async (id) => {
    if (!newsStore.detailMap[id]) {
      await newsStore.loadDetail(id);
    }
  },
);
</script>

<template>
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h1 class="page-title">News Detail</h1>
        <p class="page-subtitle">查看单条新闻的情绪、AI 影响判断、关联股票和所属主题。</p>
      </div>
      <StaleBadge :stale="newsStore.stale" label="新闻详情" />
    </header>

    <LoadingBlock :loading="newsStore.detailLoading" :empty="!detail" empty-text="新闻不存在或详情尚不可用">
      <div v-if="detail" class="grid gap-4" data-role="news-detail-layout">
        <SectionCard :title="detail.title" :subtitle="detailSummary ?? '摘要待补充'">
          <div class="detail-header-actions">
            <div class="flex flex-wrap gap-2 text-muted">
              <span class="pill" :class="detail.sentiment_label">{{ sentimentText(detail.sentiment_label) }}</span>
              <span>{{ detail.source_name }}</span>
              <span>{{ formatMarketTime(getNewsDisplayTimestamp(detail), detail.market) }} {{ getMarketTimezoneLabel(detail.market) }}</span>
            </div>
            <div class="flex items-center gap-2.5 flex-wrap w-full md:w-auto">
              <a
                v-if="detail.canonical_url"
                :href="detail.canonical_url"
                target="_blank"
                rel="noreferrer"
                class="detail-primary-action"
                data-role="open-source-link"
              >
                打开原文
              </a>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="关联信息" subtitle="股票命中和主题聚合入口">
          <div class="flex flex-wrap gap-2 text-muted">
            <span v-for="mention in detail.mentions" :key="`${mention.symbol}-${mention.mention_type}`" class="pill neutral">
              {{ mention.symbol }} · {{ Math.round(mention.confidence * 100) }}%
            </span>
            <span v-if="detail.mentions.length === 0" class="text-text-faint">暂无股票关联</span>
          </div>
          <button
            v-if="detail.topic"
            class="mt-3 rounded-full bg-accent px-[14px] py-2.5 font-semibold text-bg"
            type="button"
            @click="openTopic(detail.topic.id)"
          >
            查看主题：{{ detail.topic.topic_title }}
          </button>
        </SectionCard>

        <NewsAiImpactCard :news-id="newsId" />

        <SectionCard title="同主题来源导航" subtitle="在同一主题下顺序切换不同来源，便于横向对比">
          <div v-if="topicDetail && currentTopicIndex >= 0" class="grid gap-3">
            <div class="grid gap-1 text-muted">
              <strong>{{ topicDetail.topic_title }}</strong>
              <span class="num">当前第 {{ currentTopicIndex + 1 }} / {{ topicDetail.sources.length }} 条来源</span>
            </div>
            <div class="flex flex-wrap gap-2.5">
              <button
                class="rounded-full bg-accent px-[14px] py-2.5 font-semibold text-bg disabled:cursor-not-allowed disabled:opacity-45"
                type="button"
                :disabled="!previousSource"
                @click="previousSource && openSibling(previousSource.id)"
              >
                上一条来源
              </button>
              <button
                class="rounded-full bg-accent px-[14px] py-2.5 font-semibold text-bg disabled:cursor-not-allowed disabled:opacity-45"
                type="button"
                :disabled="!nextSource"
                @click="nextSource && openSibling(nextSource.id)"
              >
                下一条来源
              </button>
            </div>
          </div>
          <p v-else class="text-text-faint">当前新闻尚未关联到可导航的主题来源列表。</p>
        </SectionCard>
      </div>
    </LoadingBlock>
  </div>
</template>

<style scoped>
.detail-header-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.detail-primary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  padding: 0 16px;
  border-radius: 999px;
  background: var(--accent);
  color: var(--bg);
  font-weight: 600;
  text-decoration: none;
  transition: transform 160ms ease, box-shadow 160ms ease;
}

.detail-primary-action:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px color-mix(in srgb, var(--accent) 24%, transparent);
}

@media (max-width: 720px) {
  .detail-header-actions {
    align-items: stretch;
  }

  .detail-primary-action {
    width: 100%;
  }
}
</style>
