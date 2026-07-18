<script setup lang="ts">
import { computed, onMounted } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import { useDigestStore } from '../stores/digestStore';
import { parseMarkdown } from '../utils/markdown';
import { formatMarketTime } from '../utils/time';

const digestStore = useDigestStore();

const marketOptions = [
  { label: '全市场', value: 'all' as const },
  { label: '港股', value: 'hk' as const },
  { label: '美股', value: 'us' as const },
];

const generatedByLabel = computed(() => {
  if (!digestStore.digest) return '';
  return digestStore.digest.generated_by === 'llm' ? 'LLM 生成' : '规则汇总';
});

const generatedAtLabel = computed(() => {
  if (!digestStore.digest?.generated_at) return null;
  return formatMarketTime(digestStore.digest.generated_at, 'hk');
});

async function handleGenerate() {
  try {
    await digestStore.generate();
  } catch {
    // 错误已由 store 记录
  }
}

onMounted(() => {
  void digestStore.loadLatest();
});
</script>

<template>
  <div class="grid gap-4">
    <header>
      <h1 class="page-title">每日盘前/盘后 AI 简报</h1>
      <p class="page-subtitle">
        定时汇总隔夜/当日重点、自选股相关新闻与整体情绪方向，帮助你不必一直盯盘。
      </p>
    </header>

    <SectionCard title="生成控制" subtitle="选择市场范围后可立即生成一份最新简报">
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-1.5" data-role="digest-market-tabs">
          <button
            v-for="option in marketOptions"
            :key="option.value"
            class="rounded-full border px-3.5 py-1.5 text-sm font-semibold transition"
            :class="
              digestStore.marketScope === option.value
                ? 'border-accent/40 bg-accent/10 text-text'
                : 'border-border bg-white/[0.02] text-muted hover:border-system/20 hover:text-text'
            "
            :disabled="digestStore.generating"
            @click="digestStore.marketScope = option.value"
          >
            {{ option.label }}
          </button>
        </div>
        <button
          class="rounded-full bg-accent px-5 py-2 font-semibold text-bg disabled:cursor-not-allowed disabled:opacity-50"
          data-role="digest-generate-button"
          :disabled="digestStore.generating"
          @click="handleGenerate"
        >
          {{ digestStore.generating ? '正在生成…' : '立即生成' }}
        </button>
        <p v-if="digestStore.error" class="text-sm text-danger">{{ digestStore.error }}</p>
      </div>
    </SectionCard>

    <div v-if="digestStore.loading && !digestStore.digest" class="text-text-faint">正在加载最新简报…</div>

    <SectionCard
      v-else-if="digestStore.digest"
      :title="digestStore.digest.title"
      :subtitle="`${generatedByLabel}${generatedAtLabel ? ' · ' + generatedAtLabel + ' HKT' : ''}`"
      data-role="digest-card"
    >
      <div class="grid gap-4">
        <article
          v-for="section in digestStore.digest.sections"
          :key="section.title"
          class="rounded-[16px] border border-border bg-white/[0.02] p-4"
          data-role="digest-section"
        >
          <h3 class="mb-2 text-[15px] font-semibold text-text">{{ section.title }}</h3>
          <div
            class="text-sm leading-relaxed text-text-muted [&_p]:mb-2 [&_ul]:my-1"
            v-html="parseMarkdown(section.body)"
          />
        </article>
      </div>
    </SectionCard>

    <SectionCard v-else title="暂无简报" subtitle="尚未生成任何简报">
      <p class="text-text-faint">
        点击上方「立即生成」即可生成第一份简报；开启定时 worker 后，系统会在盘前/盘后自动生成并推送到飞书。
      </p>
    </SectionCard>
  </div>
</template>
