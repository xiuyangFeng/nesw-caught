<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';

import SectionCard from '../components/common/SectionCard.vue';
import { reasonLabel, sleeveLabel } from '../constants/quantLabels';
import { apiClient } from '../api/client';
import type { QuantProposal, QuantProposalExecute } from '../types/api';

const router = useRouter();
const proposal = ref<QuantProposal | null>(null);
const error = ref<string | null>(null);
const executing = ref(false);
const confirmOpen = ref(false);
const result = ref<QuantProposalExecute | null>(null);

const hasPositions = computed(() => (proposal.value?.items ?? []).length > 0);

async function load() {
  try {
    const response = await apiClient.getQuantProposal();
    proposal.value = response.data;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '组合提案加载失败';
  }
}

function openConfirm() {
  confirmOpen.value = true;
  error.value = null;
}

function closeConfirm() {
  confirmOpen.value = false;
}

async function handleExecute() {
  if (executing.value) return;
  executing.value = true;
  error.value = null;
  try {
    const response = await apiClient.executeQuantProposal();
    result.value = response.data;
    confirmOpen.value = false;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '下单失败';
    confirmOpen.value = false;
  } finally {
    executing.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-proposal-view">
    <header>
      <h1 class="page-title">组合提案</h1>
      <p class="page-subtitle">目标仓位由分配器给出；排名不等于仓位，LLM 不改权重。</p>
    </header>
    <p v-if="error" class="text-sm text-danger" data-role="desk-proposal-error">{{ error }}</p>
    <SectionCard eyebrow="Allocation" title="现金与约束" subtitle="单票 ≤8%、单 sleeve ≤50%、现金 ≥10%">
      <p class="text-sm text-text" data-role="desk-proposal-cash">
        现金 {{ Math.round((proposal?.cash_weight ?? 1) * 100) }}%
      </p>
      <p class="mt-2 text-sm text-muted">{{ proposal?.note ?? '无合格机会时现金为 100%。' }}</p>
    </SectionCard>
    <SectionCard eyebrow="Positions" title="建议仓位">
      <p v-if="!hasPositions" class="text-sm text-muted" data-role="desk-proposal-empty">当前无建议仓位，保持现金。</p>
      <template v-else>
        <table class="w-full text-left text-sm" data-role="desk-proposal-items">
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
              <td class="py-1">{{ sleeveLabel(item.sleeve) }}</td>
              <td class="py-1 tabular-nums">{{ (item.weight * 100).toFixed(1) }}%</td>
              <td class="py-1 text-muted">{{ item.reject_reason ? reasonLabel(item.reject_reason) : '—' }}</td>
            </tr>
          </tbody>
        </table>
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            class="rounded-md border border-accent px-3 py-1.5 text-sm text-accent"
            :disabled="executing"
            data-role="desk-proposal-execute"
            @click="openConfirm"
          >
            按提案下单到模拟盘
          </button>
          <RouterLink class="text-sm text-accent" to="/portfolio">查看模拟盘</RouterLink>
        </div>
      </template>
    </SectionCard>

    <SectionCard v-if="result" eyebrow="Execution" title="下单结果" data-role="desk-proposal-execute-result">
      <p class="text-sm text-muted">现金仓位不参与下单。A 股按 100 股整数倍换算。</p>
      <ul class="mt-3 grid gap-2 text-sm" data-role="desk-proposal-execute-list">
        <li v-for="order in result.orders" :key="`${order.symbol}-${order.sleeve}`">
          <span class="text-text">{{ order.symbol }}</span>
          <span class="text-muted">
            · {{ order.filled ? `成交 ${order.shares} 股 @ ${order.fill_price?.toFixed(2)}` : `未成交（${reasonLabel(order.reject_reason)}）` }}
          </span>
        </li>
      </ul>
      <RouterLink class="mt-3 inline-block text-sm text-accent" to="/portfolio">去模拟盘查看持仓</RouterLink>
    </SectionCard>

    <div v-if="confirmOpen" class="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4" data-role="desk-proposal-confirm-backdrop" @click.self="closeConfirm">
      <div class="w-full max-w-md rounded-lg border border-border bg-panel p-4 shadow-lg" data-role="desk-proposal-confirm">
        <h2 class="font-medium text-text">确认按提案下单？</h2>
        <p class="mt-1 text-sm text-muted">将按下列权重换算股数（100 股整数倍）逐条买入模拟盘；无行情或未达 1 手将自动拒单。</p>
        <ul class="mt-3 grid gap-1.5 text-sm" data-role="desk-proposal-confirm-list">
          <li v-for="item in proposal?.items" :key="`confirm-${item.symbol}`" class="flex items-center justify-between">
            <span class="text-text">{{ item.symbol }}</span>
            <span class="num text-muted">{{ (item.weight * 100).toFixed(1) }}%</span>
          </li>
        </ul>
        <div class="mt-4 flex justify-end gap-2">
          <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm" data-role="desk-proposal-confirm-cancel" @click="closeConfirm">取消</button>
          <button type="button" class="rounded-md border border-accent px-3 py-1.5 text-sm text-accent" :disabled="executing" data-role="desk-proposal-confirm-ok" @click="handleExecute">
            {{ executing ? '下单中…' : '确认下单' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
