<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import type { QuantResearchPack } from '../types/api';

const route = useRoute();
const router = useRouter();
const pack = ref<QuantResearchPack | null>(null);
const error = ref<string | null>(null);

const symbol = computed(() => String(route.params.symbol ?? '').toUpperCase());

async function load() {
  if (!symbol.value) return;
  try {
    const response = await apiClient.getQuantResearch(symbol.value);
    pack.value = response.data;
    error.value = null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '研究包加载失败';
  }
}

function askAi() {
  void router.push({ path: '/chat', query: { desk_symbol: symbol.value } });
}

onMounted(() => {
  void load();
});

watch(symbol, () => {
  void load();
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-stock-view">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="page-title">个股研究 {{ symbol }}</h1>
        <p class="page-subtitle">纵横研究包回答必答问题；缺财务时显式缺口，不编造数字。</p>
      </div>
      <button
        type="button"
        class="rounded-md px-3 py-1.5 text-sm text-white"
        style="background: #8b7cff"
        data-role="desk-ask-ai"
        @click="askAi"
      >
        问 AI
      </button>
    </header>
    <p v-if="error" class="text-sm text-danger">{{ error }}</p>
    <SectionCard
      v-for="module in pack?.modules ?? []"
      :key="module.key"
      :eyebrow="module.key"
      :title="module.question"
    >
      <p class="text-sm text-text">{{ module.answer }}</p>
      <p v-if="module.gap" class="mt-2 text-xs text-warning">缺口：{{ module.gap }}</p>
      <p v-if="module.evidence_ids?.length" class="mt-2 text-xs text-muted">证据 {{ module.evidence_ids.join(', ') }}</p>
    </SectionCard>
    <p class="text-xs text-muted">副驾工具白名单只读：资金流、研究包、新闻检索、策略预览、回测报告、成绩单。不能下单或改策略。</p>
  </div>
</template>
