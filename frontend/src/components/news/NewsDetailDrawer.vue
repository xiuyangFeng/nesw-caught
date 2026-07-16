<script setup lang="ts">
import { computed, watch, onMounted } from 'vue';
import { RouterLink } from 'vue-router';
import { useNewsStore } from '../../stores/newsStore';
import { useLlmStore } from '../../stores/llmStore';
import LoadingBlock from '../common/LoadingBlock.vue';
import { formatMarketTime, getMarketTimezoneLabel, getNewsDisplayTimestamp } from '../../utils/time';

const props = defineProps<{
  newsId: number | null;
  visible: boolean;
  filteredNewsIds: number[];
}>();

const emit = defineEmits<{
  (event: 'close'): void;
  (event: 'changeNews', id: number): void;
}>();

const newsStore = useNewsStore();
const llmStore = useLlmStore();

// 自动加载详情与 AI 研判
watch(
  () => props.newsId,
  (newId) => {
    if (newId !== null) {
      newsStore.loadDetail(newId);
      newsStore.loadAnalysis(newId);
    }
  },
  { immediate: true }
);

onMounted(() => {
  if (!llmStore.config) {
    llmStore.loadConfig();
  }
});

const detail = computed(() => {
  if (props.newsId === null) return null;
  return newsStore.detailMap[props.newsId] || null;
});

const analysis = computed(() => {
  if (props.newsId === null) return null;
  return newsStore.analysisMap[props.newsId] || null;
});

const analysisLoading = computed(() => {
  if (props.newsId === null) return false;
  return newsStore.analysisLoadingMap[props.newsId] || false;
});

const analysisError = computed(() => {
  if (props.newsId === null) return null;
  return newsStore.analysisErrorMap[props.newsId] || null;
});

// 上一篇/下一篇计算
const currentIndex = computed(() => {
  if (props.newsId === null) return -1;
  return props.filteredNewsIds.indexOf(props.newsId);
});

const hasPrev = computed(() => currentIndex.value > 0);
const hasNext = computed(() => currentIndex.value >= 0 && currentIndex.value < props.filteredNewsIds.length - 1);

function goPrev() {
  if (hasPrev.value) {
    emit('changeNews', props.filteredNewsIds[currentIndex.value - 1]);
  }
}

function goNext() {
  if (hasNext.value) {
    emit('changeNews', props.filteredNewsIds[currentIndex.value + 1]);
  }
}

async function runAnalysis() {
  if (props.newsId !== null) {
    try {
      await newsStore.analyzeNews(props.newsId);
    } catch (e) {
      console.error(e);
    }
  }
}

// 后端 sentiment_label 为可空 string,空值按未分析展示
function sentimentText(label: string | null | undefined) {
  const map: Record<string, string> = {
    positive: '偏利好',
    negative: '偏利空',
    neutral: '中性',
    mixed: '多空交织',
    unknown: '未分析',
  };
  return map[label ?? 'unknown'] || label || '未分析';
}
</script>

<template>
  <Teleport to="body">
    <!-- 遮罩层 -->
    <Transition name="fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-[100] bg-black/70"
        @click="emit('close')"
      />
    </Transition>

    <!-- 侧滑抽屉 -->
    <Transition name="slide">
      <div
        v-if="visible"
        class="fixed top-0 right-0 bottom-0 z-[101] w-full max-w-[500px] border-l border-border bg-panel shadow-shell flex flex-col"
        data-role="news-detail-drawer"
      >
        <!-- 抽屉头部导航 -->
        <header class="flex items-center justify-between border-b border-border px-4 py-3 shrink-0">
          <div class="flex items-center gap-1">
            <button
              class="p-1.5 rounded-full hover:bg-panel-strong text-muted hover:text-text disabled:opacity-30 disabled:cursor-not-allowed transition duration-150"
              type="button"
              :disabled="!hasPrev"
              title="上一篇"
              @click="goPrev"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-5 h-5">
                <path fill-rule="evenodd" d="M9.78 4.22a.75.75 0 0 1 0 1.06L6.56 8.5l3.22 3.22a.75.75 0 1 1-1.06 1.06L5.5 8.5l3.22-3.22a.75.75 0 0 1 1.06 0Z" clip-rule="evenodd" />
              </svg>
            </button>
            <button
              class="p-1.5 rounded-full hover:bg-panel-strong text-muted hover:text-text disabled:opacity-30 disabled:cursor-not-allowed transition duration-150"
              type="button"
              :disabled="!hasNext"
              title="下一篇"
              @click="goNext"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-5 h-5">
                <path fill-rule="evenodd" d="M6.22 4.22a.75.75 0 0 1 1.06 0L10.5 8.5l-3.22 3.22a.75.75 0 1 1-1.06-1.06L9.44 8.5 6.22 5.28a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" />
              </svg>
            </button>
            <span class="text-[11px] text-muted font-mono tabular-nums ml-2">
              第 {{ currentIndex + 1 }} / {{ filteredNewsIds.length }} 篇
            </span>
            <RouterLink
              v-if="newsId !== null"
              :to="{ name: 'news-detail', params: { id: newsId } }"
              class="text-xs text-muted hover:text-text"
              data-role="drawer-open-full"
              @click="emit('close')"
            >
              完整页 ↗
            </RouterLink>
          </div>

          <button
            class="p-1.5 rounded-full hover:bg-panel-strong text-muted hover:text-text transition duration-150"
            type="button"
            title="关闭"
            @click="emit('close')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-5 h-5">
              <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
            </svg>
          </button>
        </header>

        <!-- 抽屉滚动内容区 -->
        <main class="flex-1 overflow-y-auto p-4 space-y-4">
          <LoadingBlock :loading="newsStore.detailLoading" :empty="!detail" empty-text="未找到新闻详情">
            <div v-if="detail" class="space-y-4">
              <!-- 新闻标题与元数据 -->
              <section class="space-y-3">
                <h2 class="text-[18px] font-bold leading-snug text-text m-0">
                  {{ detail.title }}
                </h2>
                
                <div class="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                  <span class="pill" :class="detail.sentiment_label">
                    {{ sentimentText(detail.sentiment_label) }}
                  </span>
                  <span class="bg-panel-strong border border-border px-2 py-0.5 rounded-sm">
                    {{ detail.source_name }}
                  </span>
                  <span class="font-mono tabular-nums">
                    {{ formatMarketTime(getNewsDisplayTimestamp(detail), detail.market) }}
                    {{ getMarketTimezoneLabel(detail.market) }}
                  </span>
                </div>

                <div v-if="detail.canonical_url" class="pt-1">
                  <a
                    :href="detail.canonical_url"
                    target="_blank"
                    rel="noreferrer"
                    class="inline-flex items-center gap-1.5 text-[11px] font-semibold text-system hover:text-accent transition duration-150"
                  >
                    <span>打开原文网页</span>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
                      <path fill-rule="evenodd" d="M8.914 6.025a.75.75 0 0 1 1.06 0L13.5 9.548a.75.75 0 0 1 0 1.06l-3.525 3.525a.75.75 0 1 1-1.06-1.06L11.939 10.5 8.914 7.475a.75.75 0 0 1 0-1.06Z" clip-rule="evenodd" />
                      <path fill-rule="evenodd" d="M12.5 10a.75.75 0 0 1-.75-.75V3.5a.75.75 0 0 0-.75-.75H3.5a.75.75 0 0 1 0-1.5h7.5A2.25 2.25 0 0 1 13.25 3.5v5.75a.75.75 0 0 1-.75.75Z" clip-rule="evenodd" />
                    </svg>
                  </a>
                </div>
              </section>

              <!-- 股票提及 (Mentions) -->
              <section class="rounded-md border border-border bg-panel-strong p-3 space-y-2">
                <div class="label-mono text-muted">关联股票</div>
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="mention in detail.mentions"
                    :key="`${mention.symbol}-${mention.mention_type}`"
                    class="text-[11px] font-mono tabular-nums px-2 py-0.5 bg-panel-soft border border-border rounded-sm text-text-soft"
                  >
                    {{ mention.symbol }} ({{ Math.round(mention.confidence * 100) }}%)
                  </span>
                  <span v-if="detail.mentions.length === 0" class="text-[11px] text-text-faint">
                    暂无股票关联
                  </span>
                </div>
              </section>

              <!-- 新闻正文区 (Article Body) -->
              <section class="space-y-2">
                <div class="label-mono text-muted">新闻正文</div>
                <div class="rounded-md border border-border bg-field p-3.5 max-h-[200px] overflow-y-auto">
                  <p
                    v-if="detail.article?.content_text"
                    class="m-0 text-[12px] leading-relaxed text-text-soft whitespace-pre-wrap"
                  >
                    {{ detail.article.content_text }}
                  </p>
                  <p v-else class="m-0 text-[12px] text-text-faint italic">
                    该新闻无抓取的正文内容，已展示标题和摘要。
                  </p>
                </div>
              </section>

              <!-- LLM AI 研判面板 (AI Analysis) -->
              <section class="border-t border-border pt-3 space-y-3">
                <div class="flex items-center justify-between">
                  <div class="inline-flex items-center gap-1.5 label-mono text-ai">
                    <span aria-hidden="true">✦</span>大模型解读 · AI INSIGHT
                  </div>

                  <!-- 魔棒 AI 研判按钮 -->
                  <button
                    v-if="llmStore.config?.configured"
                    class="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 bg-[var(--ai-soft)] border border-border hover:border-ai rounded-full text-ai transition duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
                    type="button"
                    :disabled="analysisLoading"
                    @click="runAnalysis"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
                      <path d="M10.28 1.47a.75.75 0 0 1 1.06 0l3.19 3.19a.75.75 0 0 1 0 1.06l-2.03 2.03-4.25-4.25 2.03-2.03ZM9.44 4.56l4.25 4.25-6.72 6.72a2.25 2.25 0 0 1-1.07.6l-2.73.55a.75.75 0 0 1-.88-.88l.55-2.73a2.25 2.25 0 0 1 .6-1.07L9.44 4.56Z" />
                    </svg>
                    <span>{{ analysis ? '重新解读' : '一键 AI 解读' }}</span>
                  </button>
                </div>

                <div v-if="analysisLoading" class="text-[12px] text-text-faint italic py-2 flex items-center gap-2">
                  <span class="animate-pulse h-1.5 w-1.5 bg-ai rounded-full"></span>
                  正在运行深度大模型分析逻辑...
                </div>
                <div v-else-if="analysisError" class="text-[12px] text-danger bg-[var(--danger-soft)] border border-border rounded-md px-3 py-2">
                  {{ analysisError }}
                </div>
                <div v-else-if="analysis" class="space-y-3">
                  <!-- Top Pick Card -->
                  <div
                    v-if="analysis.top_pick"
                    class="rounded-md border border-border bg-[var(--positive-soft)] p-3 space-y-1.5"
                  >
                    <div class="label-mono text-positive">首选影响标的 · TOP PICK</div>
                    <div class="flex items-baseline gap-2">
                      <h3 class="text-[16px] font-mono font-bold text-text m-0">{{ analysis.top_pick.symbol }}</h3>
                      <span v-if="analysis.top_pick.company_name" class="text-[11px] text-text-faint">
                        {{ analysis.top_pick.company_name }}
                      </span>
                      <span class="text-[10px] font-mono tabular-nums bg-[var(--positive-soft)] text-positive px-1.5 py-0.5 rounded-sm ml-auto">
                        置信度 {{ Math.round((analysis.top_pick.confidence ?? 0) * 100) }}%
                      </span>
                    </div>
                    <p class="m-0 text-[12px] text-text-soft leading-relaxed">
                      {{ analysis.top_pick.reason }}
                    </p>
                  </div>

                  <!-- AI Summary & Risks -->
                  <div class="grid gap-3 text-[12px] bg-panel-soft border border-border p-3 rounded-md">
                    <div>
                      <strong class="block text-text font-bold mb-1">事件驱动摘要</strong>
                      <p class="m-0 text-text-soft leading-relaxed">{{ analysis.summary || '暂无分析摘要' }}</p>
                    </div>
                    <div class="border-t border-border pt-2.5">
                      <strong class="block text-text font-bold mb-1">主要潜在风险</strong>
                      <p class="m-0 text-text-soft leading-relaxed">{{ analysis.risk_notes || '暂无风险提示' }}</p>
                    </div>
                  </div>

                  <!-- Other Candidates -->
                  <div v-if="analysis.candidates && analysis.candidates.length > 1" class="space-y-2">
                    <div class="label-mono text-muted">其余候选影响链</div>
                    <div class="space-y-2">
                      <div
                        v-for="candidate in analysis.candidates.filter(c => c.symbol !== analysis?.top_pick?.symbol)"
                        :key="`${candidate.symbol}-${candidate.market}`"
                        class="p-2.5 border border-border bg-panel-soft rounded-md space-y-1"
                      >
                        <div class="flex items-center justify-between">
                          <strong class="text-[12px] font-mono text-text-soft">{{ candidate.symbol }}</strong>
                          <span class="text-[10px] font-mono tabular-nums text-muted">{{ Math.round((candidate.confidence ?? 0) * 100) }}% 置信度</span>
                        </div>
                        <p class="m-0 text-[11px] text-text-faint leading-normal">{{ candidate.reason }}</p>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else-if="!llmStore.config?.configured" class="text-[11px] text-text-faint bg-panel-soft border border-border p-3 rounded-md italic">
                  提示：尚未配置大模型提供商 API 密钥，请在 LLM 选项中配置。
                </div>
                <div v-else class="text-[11px] text-text-faint bg-panel-soft border border-border p-3 rounded-md italic">
                  此新闻尚未请求大模型标的研判，点击上方“一键 AI 解读”即可生成。
                </div>
              </section>
            </div>
          </LoadingBlock>
        </main>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* 遮罩层淡入淡出 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 抽屉从右侧滑出 */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
