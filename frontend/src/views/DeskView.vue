<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

import LoadingBlock from '../components/common/LoadingBlock.vue';
import SectionCard from '../components/common/SectionCard.vue';
import StatusBanner from '../components/common/StatusBanner.vue';
import {
  RUN_STATUS_LABELS,
  SLEEVE_LABELS,
  TRIGGER_LABELS,
  gradeLabel,
  reasonLabel,
  stateLabel,
  tQuant,
} from '../constants/quantLabels';
import { useDeskStore } from '../stores/deskStore';

const deskStore = useDeskStore();

const sleeveLabels = SLEEVE_LABELS;

// 机会卡展开态：默认收起，点击展开因子分解（翻译后的结构化展示）。
const expanded = ref<Record<string, boolean>>({});

function toggleExpand(key: string) {
  expanded.value[key] = !expanded.value[key];
}

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
  return tQuant(RUN_STATUS_LABELS, status);
});

const cashLabel = computed(() => `${Math.round((deskStore.proposal.cash_weight ?? 1) * 100)}% 现金`);

// ---- 仪表盘分区：数据覆盖率 / 三 sleeve 漏斗 / 最近运行 / 组合提案权重 ----
const coverageWidth = computed(() => {
  const pct = deskStore.dataStatus?.coverage_pct;
  return pct == null ? 0 : Math.max(0, Math.min(100, Math.round(pct)));
});

// 漏斗横条按三 sleeve 中最大计数归一化，便于横向比较；无数据时退化为空条(合法空态)。
const funnelMaxTotal = computed(() => {
  const totals = Object.values(deskStore.sleeveCounts).map((bucket) => bucket.qualified + bucket.watch);
  return Math.max(1, ...totals);
});

function funnelWidth(count: number): number {
  return Math.round((count / funnelMaxTotal.value) * 100);
}

const runStatusTone = computed<'success' | 'warning' | 'danger' | 'neutral'>(() => {
  const status = deskStore.latest.run?.status ?? deskStore.dataStatus?.last_run_status;
  if (status === 'ok') return 'success';
  if (status === 'degraded') return 'warning';
  if (status === 'failed') return 'danger';
  return 'neutral';
});

function formatRunTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(iso) ? iso : `${iso}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('zh-CN', { hour12: false });
}

const cashWidth = computed(() =>
  Math.max(0, Math.min(100, Math.round((deskStore.proposal.cash_weight ?? 1) * 100))),
);

const emptyTitle = computed(() => {
  if (deskStore.latest.empty_reason === 'no_run_yet') return '今日无正期望机会';
  if (deskStore.latest.empty_reason === 'no_positive_edge') return '今日无正期望机会';
  if (!deskStore.hasQualified) return '今日无正期望机会';
  return '';
});

async function handleRerun() {
  try {
    await deskStore.rerun('real');
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
        <span data-role="desk-cash-weight">{{ cashLabel }}</span>
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

    <SectionCard
      eyebrow="Dashboard"
      title="交易台仪表盘"
      subtitle="数据覆盖、三 sleeve 漏斗、最近运行与组合权重一览"
      data-role="desk-dashboard"
    >
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-md border border-border bg-panel-soft p-3" data-role="desk-dashboard-coverage">
          <p class="label-mono mb-2 text-[10px] text-muted">数据覆盖率</p>
          <strong class="num text-lg text-text">{{ coverageLabel }}</strong>
          <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-panel-strong">
            <span
              class="block h-full rounded-full bg-accent transition-[width] duration-500"
              data-role="desk-dashboard-coverage-bar"
              :style="{ width: `${coverageWidth}%` }"
            />
          </div>
          <dl class="mt-3 grid gap-1 text-xs">
            <div class="flex items-center justify-between">
              <dt class="text-muted">已回填标的</dt>
              <dd class="num text-text">{{ deskStore.dataStatus?.symbol_count ?? 0 }}</dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-muted">日线条数</dt>
              <dd class="num text-text">{{ deskStore.dataStatus?.daily_bar_count ?? 0 }}</dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-muted">最新交易日</dt>
              <dd class="num text-text">{{ deskStore.dataStatus?.last_trade_date ?? '—' }}</dd>
            </div>
          </dl>
        </div>

        <div class="rounded-md border border-border bg-panel-soft p-3" data-role="desk-dashboard-funnel">
          <p class="label-mono mb-2 text-[10px] text-muted">Sleeve 漏斗</p>
          <ul class="grid gap-2.5">
            <li v-for="(label, key) in sleeveLabels" :key="key">
              <div class="flex items-center justify-between text-xs">
                <span class="text-text">{{ label }}</span>
                <span class="text-muted">
                  合格 {{ deskStore.sleeveCounts[key]?.qualified ?? 0 }} · 观察 {{ deskStore.sleeveCounts[key]?.watch ?? 0 }}
                </span>
              </div>
              <div class="mt-1 flex h-1.5 overflow-hidden rounded-full bg-panel-strong">
                <span
                  class="block h-full bg-accent"
                  :style="{ width: `${funnelWidth(deskStore.sleeveCounts[key]?.qualified ?? 0)}%` }"
                />
                <span
                  class="block h-full bg-border-strong"
                  :style="{ width: `${funnelWidth(deskStore.sleeveCounts[key]?.watch ?? 0)}%` }"
                />
              </div>
            </li>
          </ul>
        </div>

        <div class="rounded-md border border-border bg-panel-soft p-3" data-role="desk-dashboard-run">
          <p class="label-mono mb-2 text-[10px] text-muted">最近运行</p>
          <span class="pill" :class="runStatusTone" data-role="desk-dashboard-run-badge">{{ runStatusLabel }}</span>
          <dl class="mt-3 grid gap-1 text-xs">
            <div class="flex items-center justify-between">
              <dt class="text-muted">开始</dt>
              <dd class="num text-text">{{ formatRunTime(deskStore.latest.run?.started_at) }}</dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-muted">结束</dt>
              <dd class="num text-text">{{ formatRunTime(deskStore.latest.run?.finished_at) }}</dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-muted">触发方式</dt>
              <dd class="num text-text">{{ tQuant(TRIGGER_LABELS, deskStore.latest.run?.trigger) }}</dd>
            </div>
          </dl>
        </div>

        <div class="rounded-md border border-border bg-panel-soft p-3" data-role="desk-dashboard-proposal">
          <p class="label-mono mb-2 text-[10px] text-muted">组合提案权重</p>
          <p
            v-if="!deskStore.proposal.items?.length"
            class="text-xs text-muted"
            data-role="desk-dashboard-proposal-empty"
          >
            现金 {{ cashWidth }}%：无合格机会时保持现金是合法结果。
          </p>
          <template v-else>
            <ul class="grid gap-2">
              <li v-for="item in deskStore.proposal.items" :key="`${item.sleeve}-${item.symbol}`">
                <div class="flex items-center justify-between text-xs">
                  <span class="text-text">{{ item.symbol }}</span>
                  <span class="num text-muted">{{ Math.round(item.weight * 100) }}%</span>
                </div>
                <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-panel-strong">
                  <span class="block h-full rounded-full bg-accent" :style="{ width: `${Math.round(item.weight * 100)}%` }" />
                </div>
              </li>
            </ul>
            <div class="mt-2">
              <div class="flex items-center justify-between text-xs">
                <span class="text-muted">现金</span>
                <span class="num text-muted">{{ cashWidth }}%</span>
              </div>
              <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-panel-strong">
                <span class="block h-full rounded-full bg-border-strong" :style="{ width: `${cashWidth}%` }" />
              </div>
            </div>
          </template>
        </div>
      </div>
    </SectionCard>

    <div class="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)_240px]">
      <SectionCard eyebrow="Sleeves" title="分层概览" subtitle="三 sleeve 独立计分，LLM 不改排名">
        <ul class="grid gap-2 text-sm" data-role="desk-sleeve-overview">
          <li v-for="(label, key) in sleeveLabels" :key="key">
            <span class="text-text">{{ label }}</span>
            <span class="text-muted">
              · 合格 {{ deskStore.sleeveCounts[key]?.qualified ?? 0 }}
              · 观察 {{ deskStore.sleeveCounts[key]?.watch ?? 0 }}
            </span>
          </li>
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
              data-role="desk-opportunity-item"
            >
              <p class="text-xs text-muted">
                {{ sleeveLabels[item.sleeve] ?? item.sleeve }} · {{ stateLabel(item.state) }} · {{ reasonLabel(item.reason_code) }}
              </p>
              <RouterLink class="mt-1 block font-medium text-accent" :to="`/desk/stocks/${item.symbol}`">
                {{ item.display_name || item.symbol }}
              </RouterLink>
              <p class="mt-1 text-sm text-muted">{{ item.thesis_md }}</p>
              <button
                type="button"
                class="mt-2 text-xs text-accent"
                data-role="desk-opportunity-toggle"
                @click="toggleExpand(`${item.sleeve}-${item.symbol}`)"
              >
                {{ expanded[`${item.sleeve}-${item.symbol}`] ? '收起因子分解' : '展开因子分解' }}
              </button>
              <dl v-if="expanded[`${item.sleeve}-${item.symbol}`]" class="mt-2 grid gap-1 rounded-md bg-panel-soft p-2 text-xs" data-role="desk-opportunity-breakdown">
                <div v-for="(value, key) in item.factor_breakdown" :key="String(key)" class="flex items-center justify-between">
                  <dt class="font-mono text-muted">{{ key }}</dt>
                  <dd class="num tabular-nums text-text">{{ typeof value === 'number' ? value.toLocaleString('zh-CN', { maximumFractionDigits: 4 }) : value }}</dd>
                </div>
              </dl>
            </li>
          </ul>
        </LoadingBlock>
      </SectionCard>

      <SectionCard eyebrow="Radar" title="事件雷达" subtitle="快循环来自新闻 mention；点击进入研究页">
        <p class="text-sm text-muted" data-role="desk-radar-note">
          {{ deskStore.radar?.note ?? '暂无实时事件。' }}
        </p>
        <ul v-if="(deskStore.radar?.candidates ?? []).length" class="mt-3 grid gap-2 text-sm" data-role="desk-radar-list">
          <li v-for="item in deskStore.radar?.candidates" :key="`${item.symbol}-${item.news_id ?? item.reason_code}`">
            <RouterLink class="text-accent" :to="`/desk/stocks/${item.symbol}`">
              {{ item.display_name || item.symbol }}
            </RouterLink>
            <span class="text-muted"> · {{ gradeLabel(item.evidence_grade) }} · {{ reasonLabel(item.reason_code) }}</span>
          </li>
        </ul>
        <ul v-else-if="deskStore.watchItems.length" class="mt-3 grid gap-2 text-sm" data-role="desk-watch-list">
          <li v-for="item in deskStore.watchItems" :key="`watch-${item.symbol}`">
            <RouterLink class="text-accent" :to="`/desk/stocks/${item.symbol}`">
              {{ item.display_name || item.symbol }}
            </RouterLink>
            <span class="text-muted"> · {{ reasonLabel(item.reason_code) }}</span>
          </li>
        </ul>
      </SectionCard>
    </div>

    <SectionCard eyebrow="Portfolio" title="组合提案摘要" subtitle="单票 ≤8%、现金 ≥10%；LLM 不参与权重">
      <p class="text-sm text-text" data-role="desk-proposal-summary">
        {{ cashLabel }}。{{ deskStore.proposal.note ?? '合格机会为 0 时，建议保持现金。' }}
      </p>
      <RouterLink class="mt-2 inline-block text-sm text-accent" to="/desk/portfolio-proposal">查看完整提案</RouterLink>
    </SectionCard>
  </div>
</template>
