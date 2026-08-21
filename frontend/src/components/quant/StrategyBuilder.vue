<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';

import type { QuantFactor } from '../../types/api';

// 条件组合器 DSL 的结构化构建器：
// - 常规模式：sleeve/horizon/逻辑词下拉 + 因子/运算符/阈值条件行，产出扁平 DSL；
// - 高级模式：折叠的 JSON 编辑区（嵌套 DSL 或进阶用户的逃生口），双向同步；
// - 策略工作台与回测实验室共用，因子选项唯一来源是 GET /api/quant/factors。

interface ConditionRow {
  factor: string;
  op: string;
  value: number;
}

const props = withDefaults(
  defineProps<{
    modelValue: Record<string, unknown>;
    factors?: QuantFactor[];
  }>(),
  { factors: () => [] },
);

const emit = defineEmits<{ (e: 'update:modelValue', value: Record<string, unknown>): void }>();

const SLEEVE_OPTIONS = [
  { value: 'trend_flow', label: '趋势/资金' },
  { value: 'event_catalyst', label: '事件/催化' },
  { value: 'fundamental_revalue', label: '基本面重估' },
];
const HORIZON_OPTIONS = ['1d', '5d', '10d', '20d', '60d', '120d'];
const OP_OPTIONS = [
  { value: '>', label: '大于' },
  { value: '>=', label: '≥' },
  { value: '<', label: '小于' },
  { value: '<=', label: '≤' },
];

const FALLBACK_FACTORS: QuantFactor[] = [
  { key: 'main_inflow_1d', sleeve: 'trend_flow', horizon: '5d' },
];

const sleeve = ref<string>('trend_flow');
const horizon = ref<string>('20d');
const logic = ref<'and' | 'or'>('and');
// 行用 reactive 数组：行内字段随 v-model 响应式更新，watch 才能感知行编辑。
const rows = reactive<ConditionRow[]>([{ factor: 'main_inflow_1d', op: '>', value: 0 }]);
// 当前 DSL 含嵌套条件：构建器行编辑无法完整表达，只允许在高级模式改写。
const nested = ref(false);

const advancedOpen = ref(false);
const advancedText = ref('');
const advancedError = ref<string | null>(null);

const factorOptions = computed<QuantFactor[]>(() =>
  props.factors.length ? props.factors : FALLBACK_FACTORS,
);

function fromDsl(dsl: Record<string, unknown>): void {
  nested.value = false;
  sleeve.value = typeof dsl.sleeve === 'string' ? dsl.sleeve : 'trend_flow';
  horizon.value = typeof dsl.horizon === 'string' ? dsl.horizon : '20d';
  logic.value = dsl.logic === 'or' ? 'or' : 'and';
  const conditions = Array.isArray(dsl.conditions) ? dsl.conditions : [];
  const parsed: ConditionRow[] = [];
  for (const raw of conditions) {
    if (raw && typeof raw === 'object' && 'factor' in raw) {
      const cond = raw as { factor?: unknown; op?: unknown; value?: unknown };
      parsed.push({ factor: String(cond.factor ?? ''), op: String(cond.op ?? '>'), value: Number(cond.value ?? 0) });
    } else {
      nested.value = true;
    }
  }
  rows.splice(0, rows.length, ...(parsed.length ? parsed : [{ factor: factorOptions.value[0]?.key ?? 'main_inflow_1d', op: '>', value: 0 }]));
}

function toDsl(): Record<string, unknown> {
  return {
    sleeve: sleeve.value,
    horizon: horizon.value,
    logic: logic.value,
    conditions: rows.map((row) => ({ factor: row.factor, op: row.op, value: row.value })),
  };
}

// 值未变化不重复 emit：这是阻断「emit → 父更新 props → 再 emit」递归循环的关键。
function emitIfChanged(): void {
  const next = toDsl();
  if (JSON.stringify(next) !== JSON.stringify(props.modelValue ?? {})) {
    emit('update:modelValue', next);
  }
}

watch(
  () => props.modelValue,
  (value) => fromDsl(value ?? {}),
  { immediate: true, deep: true },
);

watch([sleeve, horizon, logic], () => emitIfChanged());
watch(rows, () => emitIfChanged(), { deep: true });

function addRow(): void {
  rows.push({ factor: factorOptions.value[0]?.key ?? 'main_inflow_1d', op: '>', value: 0 });
}

function removeRow(index: number): void {
  if (rows.length <= 1) return;
  rows.splice(index, 1);
}

function toggleAdvanced(): void {
  advancedOpen.value = !advancedOpen.value;
  if (advancedOpen.value) {
    advancedText.value = JSON.stringify(props.modelValue ?? {}, null, 2);
    advancedError.value = null;
  }
}

function applyAdvanced(): void {
  try {
    const parsed = JSON.parse(advancedText.value) as Record<string, unknown>;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      advancedError.value = 'DSL 必须是 JSON 对象';
      return;
    }
    advancedError.value = null;
    emit('update:modelValue', parsed);
    fromDsl(parsed);
  } catch {
    advancedError.value = 'JSON 无法解析';
  }
}
</script>

<template>
  <div class="grid gap-3" data-role="strategy-builder-root">
    <div class="flex flex-wrap gap-3 text-sm">
      <label class="grid gap-1">
        <span class="text-muted">Sleeve</span>
        <select v-model="sleeve" class="rounded-md border border-border bg-panel px-2 py-1.5" data-role="strategy-builder-sleeve">
          <option v-for="option in SLEEVE_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <label class="grid gap-1">
        <span class="text-muted">持有期限</span>
        <select v-model="horizon" class="rounded-md border border-border bg-panel px-2 py-1.5" data-role="strategy-builder-horizon">
          <option v-for="option in HORIZON_OPTIONS" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label class="grid gap-1">
        <span class="text-muted">条件逻辑</span>
        <select v-model="logic" class="rounded-md border border-border bg-panel px-2 py-1.5" data-role="strategy-builder-logic">
          <option value="and">全部满足（AND）</option>
          <option value="or">任一满足（OR）</option>
        </select>
      </label>
    </div>

    <ul class="grid gap-2" data-role="strategy-builder-rows">
      <li
        v-for="(row, index) in rows"
        :key="index"
        class="flex flex-wrap items-end gap-2 text-sm"
        data-role="strategy-builder-row"
      >
        <label class="grid gap-1">
          <span class="text-muted">因子</span>
          <select v-model="row.factor" class="rounded-md border border-border bg-panel px-2 py-1.5" data-role="strategy-builder-factor">
            <option v-for="factor in factorOptions" :key="factor.key" :value="factor.key">{{ factor.key }}</option>
          </select>
        </label>
        <label class="grid gap-1">
          <span class="text-muted">运算</span>
          <select v-model="row.op" class="rounded-md border border-border bg-panel px-2 py-1.5" data-role="strategy-builder-op">
            <option v-for="option in OP_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </label>
        <label class="grid gap-1">
          <span class="text-muted">阈值</span>
          <input
            v-model.number="row.value"
            type="number"
            step="any"
            class="w-40 rounded-md border border-border bg-panel px-2 py-1.5 tabular-nums"
            data-role="strategy-builder-value"
          />
        </label>
        <button
          type="button"
          class="rounded-md border border-border px-2 py-1.5 text-muted"
          :disabled="rows.length <= 1"
          data-role="strategy-builder-remove"
          @click="removeRow(index)"
        >
          删除
        </button>
      </li>
    </ul>

    <div class="flex flex-wrap gap-2">
      <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm" data-role="strategy-builder-add" @click="addRow">+ 增加条件</button>
      <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm" data-role="strategy-builder-advanced-toggle" @click="toggleAdvanced">
        {{ advancedOpen ? '收起高级模式' : '高级模式（JSON）' }}
      </button>
    </div>

    <p v-if="nested" class="text-xs text-warning" data-role="strategy-builder-nested-note">
      当前策略含嵌套条件，构建器无法完整表达；请在高级模式（JSON）中编辑。
    </p>

    <div v-if="advancedOpen" class="grid gap-2" data-role="strategy-builder-advanced">
      <textarea
        v-model="advancedText"
        class="min-h-[140px] w-full rounded-md border border-border bg-panel p-3 font-mono text-xs"
        data-role="strategy-builder-advanced-text"
      />
      <div class="flex items-center gap-2">
        <button type="button" class="rounded-md border border-accent px-3 py-1.5 text-sm text-accent" data-role="strategy-builder-advanced-apply" @click="applyAdvanced">应用 JSON</button>
        <p v-if="advancedError" class="text-xs text-danger" data-role="strategy-builder-advanced-error">{{ advancedError }}</p>
      </div>
    </div>
  </div>
</template>
