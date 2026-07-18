<script setup lang="ts">
import { computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import { useNewsStore } from '../stores/newsStore';
import type { NewsDetail, NewsItem, SentimentLabel } from '../types/api';
import { sentimentText } from '../utils/format';
import { getNewsSummary } from '../utils/news';
import { compareNewsTimestamps, formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../utils/time';

const route = useRoute();
const router = useRouter();
const newsStore = useNewsStore();

function normalizeSentiment(value: unknown): Extract<SentimentLabel, 'positive' | 'negative'> {
  return value === 'negative' ? 'negative' : 'positive';
}

const currentSentiment = computed(() => normalizeSentiment(route.params.sentiment));
const title = computed(() => `${sentimentText(currentSentiment.value)}新闻`);
const subtitle = computed(() =>
  currentSentiment.value === 'positive'
    ? '按发布时间倒序查看利好向新闻，并保留完整摘要与提及标的。'
    : '按发布时间倒序查看风险向新闻，并保留完整摘要与提及标的。',
);

function getCardDetail(item: NewsItem): NewsDetail | null {
  return newsStore.detailMap[item.id] ?? null;
}

const orderedItems = computed(() =>
  [...newsStore.sentimentItems].sort((left, right) => compareNewsTimestamps(left, right)),
);

async function hydrateVisibleDetails() {
  const idsToLoad = orderedItems.value
    .slice(0, 12)
    .map((item) => item.id)
    .filter((id) => !newsStore.detailMap[id]);

  await Promise.all(idsToLoad.map((id) => newsStore.loadDetail(id)));
}

async function loadSentimentNews(sentiment: Extract<SentimentLabel, 'positive' | 'negative'>) {
  await newsStore.loadSentimentNews({ sentiment_label: sentiment, limit: 300 });
  await hydrateVisibleDetails();
}

function openStory(id: number) {
  router.push({ name: 'news-detail', params: { id } });
}

watch(
  currentSentiment,
  async (sentiment) => {
    await loadSentimentNews(sentiment);
  },
  { immediate: true },
);
</script>

<template>
  <div class="grid gap-4">
    <header class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div>
        <h1 class="page-title">{{ title }}</h1>
        <p class="page-subtitle">{{ subtitle }}</p>
      </div>
      <StaleBadge :stale="newsStore.sentimentStale" label="情绪新闻" />
    </header>

    <SectionCard eyebrow="Sentiment Flow" :title="title" :subtitle="`${newsStore.sentimentItems.length} 条，按时间倒序排列`">
      <LoadingBlock :loading="newsStore.sentimentLoading" :empty="orderedItems.length === 0" empty-text="当前情绪暂无新闻">
        <div class="grid gap-3" data-role="sentiment-news-list">
          <article
            v-for="item in orderedItems"
            :key="item.id"
            class="cursor-pointer rounded-[18px] border border-border bg-white/[0.03] p-[18px] transition duration-150 ease-out hover:-translate-y-px hover:border-system/60 hover:bg-panel-strong"
            data-role="sentiment-news-card"
            @click="openStory(item.id)"
          >
            <div class="mb-3 flex flex-wrap items-center gap-2 text-[12px] text-muted">
              <span class="pill" :class="item.sentiment_label">{{ sentimentText(item.sentiment_label) }}</span>
              <span>{{ item.market.toUpperCase() }}</span>
              <span>{{ item.source_name }}</span>
              <span>
                {{ formatMarketTime(getNewsDisplayTimestamp(item), item.market) }}
                {{ getMarketTimezoneLabel(item.market) }}
              </span>
            </div>

            <div class="grid gap-3 xl:grid-cols-[minmax(0,1.7fr)_minmax(180px,0.7fr)] xl:gap-5">
              <div class="grid gap-2">
                <h3 class="m-0 text-[18px] leading-[1.35]" data-role="sentiment-news-card-title">{{ item.title }}</h3>
                <p class="m-0 leading-[1.7] text-muted">
                  {{ getNewsSummary(getCardDetail(item) ?? item) ?? '摘要待补充' }}
                </p>
              </div>

              <div class="grid gap-2 border-t border-border pt-3 text-[13px] text-muted xl:border-l xl:border-t-0 xl:pl-4 xl:pt-0">
                <strong class="text-[11px] uppercase tracking-[0.16em] text-system">涉及标的</strong>
                <template v-if="getCardDetail(item)?.mentions.length">
                  <span
                    v-for="mention in getCardDetail(item)?.mentions"
                    :key="`${item.id}-${mention.symbol}-${mention.mention_type}`"
                    class="pill neutral"
                  >
                    {{ mention.symbol }}
                  </span>
                </template>
                <span v-else>暂无标的命中</span>
              </div>
            </div>
          </article>
        </div>
      </LoadingBlock>
    </SectionCard>
  </div>
</template>
