<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import SectionCard from '../components/common/SectionCard.vue';
import {
  DECISION_ACTION_LABELS,
  EMPTY_REASON_LABELS,
  TRIGGER_LABELS,
  reasonLabel,
  runStatusLabel,
  stageLabel,
  tQuant,
} from '../constants/quantLabels';
import { apiClient } from '../api/client';
import type { QuantAiAudit, QuantDataStatus, QuantDecisionLog, QuantRecommendationRun } from '../types/api';

const tab = ref<'runs' | 'data' | 'ai' | 'decisions'>('data');
const status = ref<QuantDataStatus | null>(null);
const audit = ref<QuantAiAudit | null>(null);
const runs = ref<QuantRecommendationRun[]>([]);
const decisions = ref<QuantDecisionLog | null>(null);
const error = ref<string | null>(null);

const coverageLabel = computed(() => {
  const pct = status.value?.coverage_pct;
  return pct == null ? '—' : `${pct}%`;
});

onMounted(async () => {
  try {
    const [statusRes, auditRes, runsRes, decisionsRes] = await Promise.all([
      apiClient.getQuantDataStatus(),
      apiClient.getQuantAiAudit(),
      apiClient.getQuantRuns(),
      apiClient.getQuantDecisionLog(),
    ]);
    status.value = statusRes.data;
    audit.value = auditRes.data;
    runs.value = Array.isArray(runsRes.data) ? runsRes.data : [];
    decisions.value = decisionsRes.data;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '数据健康加载失败';
  }
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-ops-view">
    <header>
      <h1 class="page-title">运行中心</h1>
      <p class="page-subtitle">量化域业务运行：数据覆盖、流水线与 AI 审计。全站基础设施仍在系统健康页。</p>
    </header>

    <div class="flex flex-wrap gap-2" data-role="desk-ops-tabs">
      <button type="button" class="rounded-md border px-3 py-1.5 text-sm" :class="tab === 'runs' ? 'border-accent text-accent' : 'border-border text-muted'" data-role="desk-ops-tab-runs" @click="tab = 'runs'">流水线 Runs</button>
      <button type="button" class="rounded-md border px-3 py-1.5 text-sm" :class="tab === 'data' ? 'border-accent text-accent' : 'border-border text-muted'" data-role="desk-ops-tab-data" @click="tab = 'data'">数据健康</button>
      <button type="button" class="rounded-md border px-3 py-1.5 text-sm" :class="tab === 'ai' ? 'border-accent text-accent' : 'border-border text-muted'" data-role="desk-ops-tab-ai" @click="tab = 'ai'">AI 审计</button>
      <button type="button" class="rounded-md border px-3 py-1.5 text-sm" :class="tab === 'decisions' ? 'border-accent text-accent' : 'border-border text-muted'" data-role="desk-ops-tab-decisions" @click="tab = 'decisions'">决策日志</button>
    </div>

    <p v-if="error" class="text-sm text-danger">{{ error }}</p>

    <SectionCard v-if="tab === 'data'" eyebrow="Coverage" title="数据健康" subtitle="独立行情库 coverage；未回填时为 0 是预期空态">
      <dl class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm" data-role="desk-ops-data-health">
        <div>
          <dt class="text-muted">覆盖率</dt>
          <dd class="mt-1 font-medium tabular-nums text-text">{{ coverageLabel }}</dd>
        </div>
        <div>
          <dt class="text-muted">日线条数</dt>
          <dd class="mt-1 font-medium tabular-nums text-text">{{ status?.daily_bar_count ?? 0 }}</dd>
        </div>
        <div>
          <dt class="text-muted">已回填标的</dt>
          <dd class="mt-1 font-medium tabular-nums text-text">{{ status?.symbol_count ?? 0 }}</dd>
        </div>
        <div>
          <dt class="text-muted">资金流行数</dt>
          <dd class="mt-1 font-medium tabular-nums text-text">{{ status?.fund_flow_count ?? 0 }}</dd>
        </div>
        <div>
          <dt class="text-muted">最近交易日</dt>
          <dd class="mt-1 font-medium tabular-nums text-text">{{ status?.last_trade_date ?? '—' }}</dd>
        </div>
        <div>
          <dt class="text-muted">最近自动运行</dt>
          <dd class="mt-1 font-medium tabular-nums text-text" data-role="desk-ops-last-scheduled">{{ status?.last_scheduled_run_date ?? '尚未自动运行' }}</dd>
        </div>
        <div class="sm:col-span-2">
          <dt class="text-muted">说明</dt>
          <dd class="mt-1 text-text">{{ status?.note ?? '加载中' }}</dd>
        </div>
      </dl>
    </SectionCard>

    <SectionCard v-else-if="tab === 'ai'" eyebrow="Audit" title="AI 审计" subtitle="角色/模型/缓存/降级；不回显 prompt 全文">
      <p class="mb-3 text-sm text-muted">{{ audit?.note }}</p>
      <table v-if="audit?.items?.length" class="w-full text-left text-sm" data-role="desk-ops-ai-audit">
        <thead class="text-muted">
          <tr>
            <th class="py-1 font-normal">角色</th>
            <th class="py-1 font-normal">模型</th>
            <th class="py-1 font-normal">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in audit.items" :key="row.id" class="text-text">
            <td class="py-1">{{ row.role }}</td>
            <td class="py-1">{{ row.model }}</td>
            <td class="py-1">{{ row.status }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-sm text-muted" data-role="desk-ops-ai-audit">暂无调用记录。</p>
    </SectionCard>

    <SectionCard v-else-if="tab === 'runs'" eyebrow="Runs" title="流水线 Runs" subtitle="阶段时间线与 result hash；同版本重跑应一致">
      <p v-if="!runs.length" class="text-sm text-muted" data-role="desk-ops-runs">尚无运行记录。可在机会雷达手动重跑。</p>
      <ul v-else class="grid gap-3" data-role="desk-ops-runs">
        <li v-for="run in runs" :key="run.id" class="rounded-md border border-border px-3 py-3 text-sm">
          <p class="font-medium text-text">
            {{ run.run_date }} · {{ runStatusLabel(run.status) }} · {{ tQuant(TRIGGER_LABELS, run.trigger) }}
            <span class="ml-2 font-mono text-xs text-faint">hash {{ run.result_hash }}</span>
          </p>
          <p class="mt-1 text-muted">{{ tQuant(EMPTY_REASON_LABELS, run.empty_reason) }}</p>
          <ul v-if="run.stages?.length" class="mt-2 grid gap-1 text-xs text-muted">
            <li v-for="stage in run.stages" :key="stage.stage">
              {{ stageLabel(stage.stage) }} · {{ stage.status === 'ok' ? '完成' : stage.status }}
            </li>
          </ul>
        </li>
      </ul>
    </SectionCard>

    <SectionCard v-else eyebrow="Decisions" title="决策日志" subtitle="模拟下单、拒绝原因与确认动作">
      <p v-if="!(decisions?.items ?? []).length" class="text-sm text-muted" data-role="desk-ops-decisions">暂无决策记录。</p>
      <ul v-else class="grid gap-2 text-sm" data-role="desk-ops-decisions">
        <li v-for="(item, index) in decisions?.items" :key="String(item.id ?? index)">
          <span class="text-text">{{ item.symbol ?? '—' }}</span>
          <span class="text-muted"> · {{ tQuant(DECISION_ACTION_LABELS, typeof item.action === 'string' ? item.action : null) }} · {{ reasonLabel(typeof item.reason === 'string' ? item.reason : null) }}</span>
        </li>
      </ul>
    </SectionCard>
  </div>
</template>
