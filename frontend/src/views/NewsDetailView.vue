<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import { useNewsStore } from '../stores/newsStore';
import { sentimentText } from '../utils/format';
import { formatMarketTime, getMarketTimezoneLabel } from '../utils/time';

const route = useRoute();
const router = useRouter();
const newsStore = useNewsStore();

const newsId = computed(() => Number(route.params.id));
const detail = computed(() => newsStore.detailMap[newsId.value] ?? null);

function openTopic(topicId: number) {
  router.push({ name: 'topic-detail', params: { id: topicId } });
}

onMounted(async () => {
  if (!detail.value) {
    await newsStore.loadDetail(newsId.value);
  }
});
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">News Detail</h1>
        <p class="page-subtitle">查看单条新闻的正文、情绪、关联股票和所属主题。</p>
      </div>
      <StaleBadge :stale="newsStore.stale" label="新闻详情" />
    </header>

    <LoadingBlock :loading="newsStore.detailLoading" :empty="!detail" empty-text="新闻不存在或详情尚不可用">
      <div v-if="detail" class="detail-layout">
        <SectionCard :title="detail.title" :subtitle="detail.summary ?? '摘要待补充'">
          <div class="meta-row">
            <span class="pill" :class="detail.sentiment_label">{{ sentimentText(detail.sentiment_label) }}</span>
            <span>{{ detail.source_name }}</span>
            <span>{{ formatMarketTime(detail.published_at, detail.market) }} {{ getMarketTimezoneLabel(detail.market) }}</span>
            <a v-if="detail.canonical_url" :href="detail.canonical_url" target="_blank" rel="noreferrer">打开原文</a>
          </div>
        </SectionCard>

        <SectionCard title="正文内容" subtitle="正文抓取失败时仍保留来源与聚合信息">
          <p class="body-text">{{ detail.article?.content_text ?? '正文暂不可用' }}</p>
          <p class="subtle">
            {{ detail.article?.extract_status ?? 'not_requested' }}
            <span v-if="detail.article?.extract_error"> · {{ detail.article.extract_error }}</span>
          </p>
        </SectionCard>

        <SectionCard title="关联信息" subtitle="股票命中和主题聚合入口">
          <div class="mention-list">
            <span v-for="mention in detail.mentions" :key="`${mention.symbol}-${mention.mention_type}`" class="pill neutral">
              {{ mention.symbol }} · {{ Math.round(mention.confidence * 100) }}%
            </span>
            <span v-if="detail.mentions.length === 0" class="subtle">暂无股票关联</span>
          </div>
          <button v-if="detail.topic" class="topic-link" type="button" @click="openTopic(detail.topic.id)">
            查看主题：{{ detail.topic.topic_title }}
          </button>
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

.meta-row,
.mention-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--muted);
}

.body-text,
.subtle {
  color: var(--muted);
}

.topic-link {
  margin-top: 12px;
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
