<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

import SectionCard from '../components/common/SectionCard.vue';
import { apiClient } from '../api/client';
import type { QuantProposal } from '../types/api';

const proposal = ref<QuantProposal | null>(null);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    const response = await apiClient.getQuantProposal();
    proposal.value = response.data;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '组合提案加载失败';
  }
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-proposal-view">
    <header>
      <h1 class="page-title">组合提案</h1>
      <p class="page-subtitle">目标仓位由分配器给出；排名不等于仓位，LLM 不改权重。</p>
    </header>
    <p v-if="error" class="text-sm text-danger">{{ error }}</p>
    <SectionCard eyebrow="Allocation" title="现金与约束" subtitle="单票 ≤8%、单 sleeve ≤50%、现金 ≥10%">
      <p class="text-sm text-text" data-role="desk-proposal-cash">
        现金 {{ Math.round((proposal?.cash_weight ?? 1) * 100) }}%
      </p>
      <p class="mt-2 text-sm text-muted">{{ proposal?.note ?? '无合格机会时现金为 100%。' }}</p>
    </SectionCard>
    <SectionCard eyebrow="Positions" title="建议仓位">
      <p v-if="!(proposal?.items ?? []).length" class="text-sm text-muted">当前无建议仓位，保持现金。</p>
      <table v-else class="w-full text-left text-sm" data-role="desk-proposal-items">
        <thead class="text-muted">
          <tr>
            <th class="py-1 font-normal">标的</th>
            <th class="py-1 font-normal">Sleeve</th>
            <th class="py-1 font-normal">权重</th>
            <th class="py-1 font-normal">拒绝原因</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in proposal?.items" :key="`${item.symbol}-${item.sleeve}`">
            <td class="py-1">
              <RouterLink class="text-accent" :to="`/desk/stocks/${item.symbol}`">{{ item.symbol }}</RouterLink>
            </td>
            <td class="py-1">{{ item.sleeve }}</td>
            <td class="py-1 tabular-nums">{{ (item.weight * 100).toFixed(1) }}%</td>
            <td class="py-1 text-muted">{{ item.reject_reason ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </SectionCard>
  </div>
</template>
