<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StaleBadge from '../components/common/StaleBadge.vue';
import { useLlmStore } from '../stores/llmStore';
import { useNewsStore } from '../stores/newsStore';
import { useTopicStore } from '../stores/topicStore';
import { sentimentText } from '../utils/format';
import { getNewsSummary } from '../utils/news';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../utils/time';

const route = useRoute();
const router = useRouter();
const newsStore = useNewsStore();
const topicStore = useTopicStore();
const llmStore = useLlmStore();

const newsId = computed(() => Number(route.params.id));
const detail = computed(() => newsStore.detailMap[newsId.value] ?? null);
const detailSummary = computed(() => (detail.value ? getNewsSummary(detail.value) : null));
const analysis = computed(() => newsStore.analysisMap[newsId.value] ?? null);
const analysisLoading = computed(() => newsStore.analysisLoadingMap[newsId.value] ?? false);
const analysisError = computed(() => newsStore.analysisErrorMap[newsId.value] ?? null);
const llmConfig = computed(() => llmStore.config);
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

async function runAnalysis() {
  await newsStore.analyzeNews(newsId.value);
}

onMounted(async () => {
  if (!detail.value) {
    await newsStore.loadDetail(newsId.value);
  }
  if (!llmConfig.value) {
    await llmStore.loadConfig();
  }
  await newsStore.loadAnalysis(newsId.value);
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
    await newsStore.loadAnalysis(id);
  },
);
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
        <SectionCard :title="detail.title" :subtitle="detailSummary ?? '摘要待补充'">
          <div class="meta-row">
            <span class="pill" :class="detail.sentiment_label">{{ sentimentText(detail.sentiment_label) }}</span>
            <span>{{ detail.source_name }}</span>
            <span>{{ formatMarketTime(getNewsDisplayTimestamp(detail), detail.market) }} {{ getMarketTimezoneLabel(detail.market) }}</span>
            <a v-if="detail.canonical_url" :href="detail.canonical_url" target="_blank" rel="noreferrer">打开原文</a>
          </div>
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

        <SectionCard title="LLM 标的分析" subtitle="手动触发单条新闻分析，返回首选标的和候选列表">
          <div v-if="llmConfig && !llmConfig.configured" class="analysis-empty">
            <strong>尚未配置 LLM</strong>
            <p class="subtle">请先在后端保存 provider、model 和 API key，之后再回来分析这条新闻。</p>
          </div>
          <div v-else class="analysis-stack">
            <div class="analysis-toolbar">
              <div class="subtle">
                <template v-if="analysis">
                  {{ analysis.provider_name }} / {{ analysis.model_name }} · {{ formatMarketTime(analysis.analyzed_at, detail.market) }}
                </template>
                <template v-else-if="llmConfig?.configured">
                  当前模型：{{ llmConfig.provider_name }} / {{ llmConfig.model_name }}
                </template>
              </div>
              <button class="topic-link" type="button" :disabled="analysisLoading" @click="runAnalysis">
                {{ analysis ? '重新分析' : '分析标的' }}
              </button>
            </div>

            <p v-if="analysisLoading" class="subtle">正在调用模型分析这条新闻...</p>
            <p v-else-if="analysisError" class="subtle">{{ analysisError }}</p>
            <div v-else-if="analysis" class="analysis-stack">
              <div v-if="analysis.top_pick" class="top-pick-card">
                <div class="analysis-label">Top Pick</div>
                <h3>{{ analysis.top_pick.symbol }}</h3>
                <p class="subtle">
                  {{ analysis.top_pick.company_name ?? '未提供公司名' }} · {{ Math.round((analysis.top_pick.confidence ?? 0) * 100) }}%
                </p>
                <p>{{ analysis.top_pick.reason }}</p>
              </div>
              <div v-else class="analysis-empty">
                <strong>暂无明确首选标的</strong>
                <p class="subtle">模型没有给出单一最值得关注的上市公司映射。</p>
              </div>

              <div class="analysis-meta-grid">
                <div>
                  <strong>摘要</strong>
                  <p class="subtle">{{ analysis.summary ?? '暂无摘要' }}</p>
                </div>
                <div>
                  <strong>风险提示</strong>
                  <p class="subtle">{{ analysis.risk_notes ?? '暂无风险提示' }}</p>
                </div>
              </div>

              <div v-if="analysis.candidates.length" class="candidate-list">
                <article v-for="candidate in analysis.candidates" :key="`${candidate.symbol}-${candidate.market}`" class="candidate-card">
                  <div class="candidate-head">
                    <strong>{{ candidate.symbol }}</strong>
                    <span class="subtle">{{ Math.round((candidate.confidence ?? 0) * 100) }}%</span>
                  </div>
                  <p class="subtle">{{ candidate.company_name ?? '未提供公司名' }}</p>
                  <p>{{ candidate.reason }}</p>
                </article>
              </div>

              <p v-if="analysis.context_limitations" class="subtle">上下文限制：{{ analysis.context_limitations }}</p>
            </div>
            <p v-else class="subtle">还没有这条新闻的分析结果，点击右侧按钮开始分析。</p>
          </div>
        </SectionCard>

        <SectionCard title="同主题来源导航" subtitle="在同一主题下顺序切换不同来源，便于横向对比">
          <div v-if="topicDetail && currentTopicIndex >= 0" class="sibling-nav">
            <div class="nav-meta">
              <strong>{{ topicDetail.topic_title }}</strong>
              <span>当前第 {{ currentTopicIndex + 1 }} / {{ topicDetail.sources.length }} 条来源</span>
            </div>
            <div class="nav-actions">
              <button class="nav-button" type="button" :disabled="!previousSource" @click="previousSource && openSibling(previousSource.id)">
                上一条来源
              </button>
              <button class="nav-button" type="button" :disabled="!nextSource" @click="nextSource && openSibling(nextSource.id)">
                下一条来源
              </button>
            </div>
          </div>
          <p v-else class="subtle">当前新闻尚未关联到可导航的主题来源列表。</p>
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

.analysis-stack {
  display: grid;
  gap: 14px;
}

.analysis-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.analysis-empty,
.top-pick-card,
.candidate-card {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: #fffdf8;
}

.analysis-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--neutral);
}

.analysis-meta-grid,
.candidate-list {
  display: grid;
  gap: 12px;
}

.candidate-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
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

.sibling-nav {
  display: grid;
  gap: 12px;
}

.nav-meta {
  display: grid;
  gap: 4px;
  color: var(--muted);
}

.nav-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.nav-button,
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

.nav-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
