<script setup lang="ts">
import { computed, onMounted } from 'vue';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import { useDeskStore } from '../stores/deskStore';

const deskStore = useDeskStore();

const sleeveLabels: Record<string, string> = {
  event_catalyst: '事件/催化',
  trend_flow: '趋势/资金',
  fundamental_revalue: '基本面重估',
};

const regimeLabel = computed(() => {
  const regime = deskStore.dataStatus?.regime ?? 'normal';
  if (regime === 'caution') return '谨慎';
  if (regime === 'defensive') return '防守';
  return '正常';
});

const coverageLabel = computed(() => {
  const pct = deskStore.dataStatus?.coverage_pct;
  return pct == null ? '覆盖率待接入' : `${Math.round(pct)}%`;
});

const runStatusLabel = computed(() => {
  const status = deskStore.latest.run?.status ?? deskStore.dataStatus?.last_run_status;
  if (!status) return '尚未运行';
  if (status === 'degraded') return '降级';
  if (status === 'failed') return '失败';
  if (status === 'running') return '运行中';
  return '正常';
});

const emptyTitle = computed(() => {
  if (deskStore.latest.empty_reason === 'no_run_yet') return '今日无正期望机会';
  if (deskStore.latest.empty_reason === 'no_positive_edge') return '今日无正期望机会';
  if (!deskStore.hasQualified) return '今日无正期望机会';
  return '';
});

async function handleRerun() {
  try {
    await deskStore.rerun('abstain');
  } catch {
    // 错误已由 store 记录
  }
}

onMounted(() => {
  void deskStore.loadDesk();
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-view">
    <header>
      <h1 class="page-title">机会雷达</h1>
      <p class="page-subtitle">
        用确定性引擎发现 0～N 个过线机会；没有正期望时现金也是合法结果。
      </p>
    </header>

    <StatusBanner
      v-if="deskStore.isDegraded"
      data-role="desk-degraded-banner"
      tone="warning"
      kicker="Degraded"
      title="本次运行为降级结果，或正在使用离线合成数据"
      :detail="deskStore.dataStatus?.note ?? '请查看未过线原因，不要把占位分数当成概率。'"
    />

    <section
      class="surface flex flex-wrap items-center justify-between gap-3 rounded-lg px-4 py-3"
      data-role="desk-status-strip"
    >
      <div class="flex flex-wrap items-center gap-4 text-sm">
        <span data-role="desk-regime">市场状态 {{ regimeLabel }}</span>
        <span data-role="desk-coverage">{{ coverageLabel }}</span>
        <span data-role="desk-run-status">最近运行 {{ runStatusLabel }}</span>
      </div>
      <button
        type="button"
        class="rounded-md border border-border bg-panel-soft px-3 py-1.5 text-sm text-text hover:bg-interactive-hover"
        data-role="desk-rerun"
        :disabled="deskStore.running"
        @click="handleRerun"
      >
        {{ deskStore.running ? '重跑中…' : '手动重跑' }}
      </button>
    </section>

    <p v-if="deskStore.error" class="text-sm text-danger" data-role="desk-error">{{ deskStore.error }}</p>

    <div class="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)_240px]">
      <SectionCard eyebrow="Sleeves" title="分层概览" subtitle="三 sleeve 独立计分，后续 Phase 补漏斗">
        <ul class="grid gap-2 text-sm text-muted" data-role="desk-sleeve-overview">
          <li v-for="(label, key) in sleeveLabels" :key="key">{{ label }} · 占位</li>
        </ul>
      </SectionCard>

      <SectionCard eyebrow="Opportunities" title="机会流" subtitle="合格机会才进入组合建议；观察池不可下单">
        <LoadingBlock :loading="deskStore.loading" :empty="false" skeleton-type="dashboard" :skeleton-count="2">
          <div
            v-if="!deskStore.hasQualified"
            class="grid min-h-[180px] place-items-center rounded-lg border border-dashed border-border bg-panel-soft p-6 text-center"
            data-role="desk-empty"
          >
            <div class="grid gap-2">
              <strong class="text-text">{{ emptyTitle }}</strong>
              <p class="text-sm text-muted">
                {{ deskStore.latest.empty_reason_detail ?? '阈值、流动性或信息可得时间未过线。' }}
              </p>
            </div>
          </div>
          <ul v-else class="grid gap-3" data-role="desk-opportunity-list">
            <li
              v-for="item in deskStore.qualifiedItems"
              :key="`${item.sleeve}-${item.symbol}`"
              class="rounded-md border border-border px-3 py-3"
            >
              <p class="text-xs text-muted">{{ sleeveLabels[item.sleeve] ?? item.sleeve }} · {{ item.state }}</p>
              <p class="mt-1 font-medium text-text">{{ item.display_name || item.symbol }}</p>
              <p class="mt-1 text-sm text-muted">{{ item.thesis_md }}</p>
            </li>
          </ul>
        </LoadingBlock>
      </SectionCard>

      <SectionCard eyebrow="Radar" title="事件雷达" subtitle="快循环将在后续 Phase 接入">
        <p class="text-sm text-muted" data-role="desk-radar-note">
          {{ deskStore.radar?.note ?? '暂无实时事件。' }}
        </p>
        <ul v-if="deskStore.watchItems.length" class="mt-3 grid gap-2 text-sm" data-role="desk-watch-list">
          <li v-for="item in deskStore.watchItems" :key="`watch-${item.symbol}`" class="text-muted">
            {{ item.display_name || item.symbol }} · {{ item.reason_code }}
          </li>
        </ul>
      </SectionCard>
    </div>

    <SectionCard eyebrow="Portfolio" title="组合提案摘要" subtitle="目标仓位与现金约束将在 Phase 3 接入">
      <p class="text-sm text-muted">当前为骨架占位。合格机会为 0 时，建议保持现金。</p>
    </SectionCard>
  </div>
</template>
