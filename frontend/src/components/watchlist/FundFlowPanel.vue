<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';

import SectionCard from '../common/SectionCard.vue';
import { apiClient } from '../../api/client';
import type { QuantFundFlow } from '../../types/api';

const props = defineProps<{
  symbol: string;
}>();

const payload = ref<QuantFundFlow | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

async function loadFlow(symbol: string) {
  loading.value = true;
  error.value = null;
  try {
    const response = await apiClient.getQuantFundFlow(symbol);
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
  <SectionCard eyebrow="Fund Flow" title="资金流" subtitle="主力净流入；无数据时为空态，不假装拥有北向个股数据">
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
          <tr v-for="point in payload.points" :key="point.trade_date" class="tabular-nums text-text">
            <td class="py-1">{{ point.trade_date }}</td>
            <td class="py-1">{{ point.main_net_inflow ?? '—' }}</td>
            <td class="py-1">{{ point.main_net_pct ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </SectionCard>
</template>
