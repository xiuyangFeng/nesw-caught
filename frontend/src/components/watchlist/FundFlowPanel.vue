<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import SectionCard from '../common/SectionCard.vue';
import { apiClient } from '../../api/client';
import type { FundFlow } from '../../types/api';
import { formatPercent } from '../../utils/format';

const props = defineProps<{
  symbol: string;
}>();

const payload = ref<FundFlow | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

// 接口返回约 60 个交易日（旧在前）；面板只展示最近 10 天，最新在上。
const RECENT_DAYS = 10;
const recentPoints = computed(() => (payload.value?.points ?? []).slice(-RECENT_DAYS).reverse());

function formatYuan(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '—';
  }
  const sign = value > 0 ? '+' : value < 0 ? '-' : '';
  const abs = Math.abs(value);
  if (abs >= 1e8) {
    return `${sign}${(abs / 1e8).toFixed(2)}亿`;
  }
  if (abs >= 1e4) {
    return `${sign}${(abs / 1e4).toFixed(2)}万`;
  }
  return `${sign}${abs.toFixed(0)}`;
}

async function loadFlow(symbol: string) {
  loading.value = true;
  error.value = null;
  try {
    const response = await apiClient.getFundFlow(symbol);
    payload.value = response.data;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '资金流加载失败';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadFlow(props.symbol);
});

watch(
  () => props.symbol,
  (next) => {
    void loadFlow(next);
  },
);
</script>

<template>
  <SectionCard eyebrow="Fund Flow" title="资金流" subtitle="最近 10 个交易日主力净流入（东财）；无数据时为空态">
    <div data-role="stock-fund-flow">
      <p v-if="loading" class="text-sm text-muted">加载资金流…</p>
      <p v-else-if="error" class="text-sm text-danger">{{ error }}</p>
      <p v-else-if="!payload?.points?.length" class="text-sm text-muted" data-role="stock-fund-flow-empty">
        {{ payload?.note ?? '暂无个股资金流。' }}
      </p>
      <table v-else class="w-full text-left text-sm">
        <thead class="text-muted">
          <tr>
            <th class="py-1 font-normal">日期</th>
            <th class="py-1 font-normal">主力净流入</th>
            <th class="py-1 font-normal">占比</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="point in recentPoints"
            :key="point.trade_date"
            class="tabular-nums text-text"
            data-role="stock-fund-flow-row"
          >
            <td class="py-1">{{ point.trade_date }}</td>
            <td class="py-1">{{ formatYuan(point.main_net_inflow) }}</td>
            <td class="py-1">{{ point.main_net_pct === null || point.main_net_pct === undefined ? '—' : formatPercent(point.main_net_pct) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </SectionCard>
</template>
