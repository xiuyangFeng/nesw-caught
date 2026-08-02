<script setup lang="ts">
import { computed, ref } from 'vue';

import SectionCard from '../common/SectionCard.vue';
import { useMarketOverviewStore } from '../../stores/marketOverviewStore';
import MarketIndexConfigModal from './MarketIndexConfigModal.vue';
import MarketOverviewCard from './MarketOverviewCard.vue';

const store = useMarketOverviewStore();

const isConfigModalOpen = ref(false);

const markets = computed(() => store.overview?.markets ?? []);
const initialLoading = computed(() => store.loading && markets.value.length === 0);

function openConfigModal() {
  isConfigModalOpen.value = true;
  void store.loadIndexConfig();
}
</script>

<template>
  <SectionCard
    title="市场总览"
    eyebrow="Market Overview"
    subtitle="美 / A / 韩 / 日 / 欧五大市场指数、板块与情绪快照,每 60 秒自动刷新"
    compact
    data-role="market-overview-panel"
  >
    <template #actions>
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="rounded-full border border-border px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-text-faint transition hover:text-text disabled:cursor-progress disabled:opacity-60"
          :disabled="store.loading"
          data-role="market-overview-refresh"
          @click="store.loadOverview()"
        >
          {{ store.loading ? '刷新中…' : '刷新' }}
        </button>
        <button
          type="button"
          class="rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-accent transition hover:bg-accent/20"
          data-role="market-overview-open-config"
          @click="openConfigModal"
        >
          配置
        </button>
      </div>
    </template>

    <p
      v-if="store.error"
      class="mb-2 rounded-[12px] border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
      data-role="market-overview-error"
    >
      {{ store.error }}
    </p>

    <div v-if="initialLoading" class="py-6 text-center text-text-faint" data-role="market-overview-loading">
      正在加载市场总览…
    </div>
    <div v-else-if="markets.length > 0" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5" data-role="market-overview-grid">
      <MarketOverviewCard v-for="market in markets" :key="market.market" :data="market" />
    </div>
    <p v-else class="py-4 text-center text-text-faint" data-role="market-overview-empty">暂无市场总览数据</p>

    <MarketIndexConfigModal :open="isConfigModalOpen" @close="isConfigModalOpen = false" />
  </SectionCard>
</template>
