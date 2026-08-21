<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';

import SectionCard from '../components/common/SectionCard.vue';
import StrategyBuilder from '../components/quant/StrategyBuilder.vue';
import EquityCurveChart from '../components/quant/EquityCurveChart.vue';
import { apiClient } from '../api/client';
import type { QuantBacktest, QuantFactor, QuantStrategy } from '../types/api';

const DEFAULT_DSL = {
  sleeve: 'trend_flow',
  horizon: '20d',
  logic: 'and',
  conditions: [{ factor: 'main_inflow_1d', op: '>', value: 50_000_000 }],
};

const route = useRoute();

const symbol = ref('');
const startDate = ref('');
const endDate = ref('');
const name = ref('实验室策略');
const dsl = ref<Record<string, unknown>>({ ...DEFAULT_DSL });
const factors = ref<QuantFactor[]>([]);
const report = ref<QuantBacktest | null>(null);
const error = ref<string | null>(null);
const running = ref(false);

const curvePoints = computed(() =>
  (report.value?.equity_curve ?? []).map((point) => ({
    date: String(point.date ?? ''),
    equity: Number(point.equity ?? 0),
  })),
);

interface TradeRow {
  signal_date?: string;
  entry_date?: string;
  entry_price?: number;
  exit_date?: string | null;
  exit_price?: number | null;
  pnl?: number | null;
}

const tradeRows = computed<TradeRow[]>(() => {
  const rows = report.value?.trades ?? [];
  return rows.map((row) => ({
    signal_date: row.signal_date != null ? String(row.signal_date) : undefined,
    entry_date: row.entry_date != null ? String(row.entry_date) : undefined,
    entry_price: row.entry_price != null ? Number(row.entry_price) : undefined,
    exit_date: row.exit_date != null ? String(row.exit_date) : null,
    exit_price: row.exit_price != null ? Number(row.exit_price) : null,
    pnl: row.pnl != null ? Number(row.pnl) : null,
  }));
});

function metricNumber(key: string): number | null {
  const value = report.value?.metrics?.[key];
  return typeof value === 'number' ? value : null;
}

function pct(value: number | null): string {
  return value == null ? '—' : `${(value * 100).toFixed(2)}%`;
}

async function loadFactors() {
  try {
    const response = await apiClient.getQuantFactors();
    factors.value = Array.isArray(response.data) ? response.data : [];
  } catch {
    factors.value = [];
  }
}

// 策略工作台「送回测」入口：?strategy=<id> 预载该策略的名称与 DSL。
async function loadPresetStrategy() {
  const strategyId = Number(route.query.strategy);
  if (!strategyId) return;
  try {
    const response = await apiClient.getQuantStrategies();
    const strategies: QuantStrategy[] = Array.isArray(response.data) ? response.data : [];
    const preset = strategies.find((item) => item.id === strategyId);
    if (preset) {
      name.value = preset.name;
      dsl.value = { ...(preset.dsl as Record<string, unknown>) };
    }
  } catch {
    // 预载失败不阻塞手工回测
  }
}

async function handleRun() {
  if (!symbol.value.trim()) {
    error.value = '请先填写回测标的代码（如 600519.SH）';
    return;
  }
  running.value = true;
  error.value = null;
  try {
    const response = await apiClient.runQuantBacktest({
      name: name.value,
      dsl: dsl.value,
      is_active: false,
      symbol: symbol.value.trim(),
      start_date: startDate.value || null,
      end_date: endDate.value || null,
    });
    report.value = response.data;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '回测失败，请检查标的代码与区间';
  } finally {
    running.value = false;
  }
}

onMounted(() => {
  void loadFactors();
  void loadPresetStrategy();
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-backtest-view">
    <header>
      <h1 class="page-title">回测实验室</h1>
      <p class="page-subtitle">自研 walk-forward，基于已回填的真实日线；探索性结果不得晋级 qualified。</p>
    </header>
    <p v-if="error" class="text-sm text-danger" data-role="desk-backtest-error">{{ error }}</p>

    <SectionCard eyebrow="Setup" title="策略与标的" subtitle="条件构建器只引用因子注册表；高级模式可编辑 JSON">
      <div class="flex flex-wrap gap-3 text-sm">
        <label class="grid gap-1">
          <span class="text-muted">标的代码</span>
          <input
            v-model="symbol"
            placeholder="600519.SH"
            class="w-44 rounded-md border border-border bg-panel px-3 py-1.5 font-mono text-xs"
            data-role="desk-backtest-symbol"
          />
        </label>
        <label class="grid gap-1">
          <span class="text-muted">开始日期</span>
          <input v-model="startDate" type="date" class="rounded-md border border-border bg-panel px-3 py-1.5" data-role="desk-backtest-start" />
        </label>
        <label class="grid gap-1">
          <span class="text-muted">结束日期</span>
          <input v-model="endDate" type="date" class="rounded-md border border-border bg-panel px-3 py-1.5" data-role="desk-backtest-end" />
        </label>
      </div>
      <div class="mt-3">
        <StrategyBuilder v-model="dsl" :factors="factors" />
      </div>
      <button
        type="button"
        class="mt-3 rounded-md border border-accent px-3 py-1.5 text-sm text-accent"
        :disabled="running"
        data-role="desk-backtest-run"
        @click="handleRun"
      >
        {{ running ? '回测中…' : '运行回测' }}
      </button>
    </SectionCard>

    <SectionCard v-if="report?.coverage_error" eyebrow="Coverage" title="数据不足" data-role="desk-backtest-coverage">
      <p class="text-sm text-warning">{{ report.coverage_error }}</p>
      <p class="mt-2 text-xs text-muted">回测不会降级为合成数据；数据不足时宁可不出报告。</p>
    </SectionCard>

    <SectionCard v-if="report && !report.coverage_error" eyebrow="Report" title="回测报告" :subtitle="report.note ?? ''" data-role="desk-backtest-report">
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-md border border-border bg-panel-soft p-3" data-role="desk-backtest-metric-return">
          <p class="label-mono mb-1 text-[10px] text-muted">区间净收益</p>
          <strong class="num text-lg tabular-nums" :class="(metricNumber('net_return') ?? 0) >= 0 ? 'text-success' : 'text-danger'">
            {{ pct(metricNumber('net_return')) }}
          </strong>
        </div>
        <div class="rounded-md border border-border bg-panel-soft p-3" data-role="desk-backtest-metric-drawdown">
          <p class="label-mono mb-1 text-[10px] text-muted">最大回撤</p>
          <strong class="num text-lg tabular-nums text-text">{{ pct(metricNumber('max_drawdown')) }}</strong>
        </div>
        <div class="rounded-md border border-border bg-panel-soft p-3" data-role="desk-backtest-metric-trades">
          <p class="label-mono mb-1 text-[10px] text-muted">完成交易</p>
          <strong class="num text-lg tabular-nums text-text">{{ metricNumber('trades') ?? 0 }} 笔</strong>
        </div>
        <div class="rounded-md border border-border bg-panel-soft p-3" data-role="desk-backtest-metric-unfilled">
          <p class="label-mono mb-1 text-[10px] text-muted">未成交信号</p>
          <strong class="num text-lg tabular-nums text-text">{{ metricNumber('unfilled') ?? 0 }} 次</strong>
        </div>
      </div>
      <p class="mt-2 text-xs text-muted" data-role="desk-backtest-meta">
        {{ report.symbol }} · 使用 {{ report.bars_used }} 根日线 · 状态 {{ report.status }} ·
        探索性 {{ report.exploratory ? '是' : '否' }} · qualified {{ report.qualified ? '是' : '否（不得晋级）' }}
      </p>
      <div class="mt-4">
        <EquityCurveChart :points="curvePoints" />
      </div>
      <div v-if="tradeRows.length" class="mt-4" data-role="desk-backtest-trades">
        <p class="label-mono mb-2 text-[10px] text-muted">交易明细（T 日信号 → T+1 开盘成交）</p>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead class="text-muted">
              <tr>
                <th class="py-1 font-normal">信号日</th>
                <th class="py-1 font-normal">入场日</th>
                <th class="py-1 font-normal">入场价</th>
                <th class="py-1 font-normal">出场日</th>
                <th class="py-1 font-normal">出场价</th>
                <th class="py-1 font-normal">单笔盈亏</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(trade, index) in tradeRows" :key="index" class="text-text">
                <td class="py-1 tabular-nums">{{ trade.signal_date ?? '—' }}</td>
                <td class="py-1 tabular-nums">{{ trade.entry_date ?? '—' }}</td>
                <td class="py-1 tabular-nums">{{ trade.entry_price?.toFixed(2) ?? '—' }}</td>
                <td class="py-1 tabular-nums">{{ trade.exit_date ?? '持仓至期末' }}</td>
                <td class="py-1 tabular-nums">{{ trade.exit_price?.toFixed(2) ?? '—' }}</td>
                <td class="py-1 tabular-nums" :class="(trade.pnl ?? 0) >= 0 ? 'text-success' : 'text-danger'">
                  {{ trade.pnl == null ? '—' : pct(trade.pnl) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </SectionCard>
  </div>
</template>
