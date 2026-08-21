<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import SectionCard from '../components/common/SectionCard.vue';
import StrategyBuilder from '../components/quant/StrategyBuilder.vue';
import { SLEEVE_LABELS, sleeveLabel } from '../constants/quantLabels';
import { apiClient } from '../api/client';
import type { QuantFactor, QuantStrategy } from '../types/api';

const DEFAULT_DSL = {
  sleeve: 'trend_flow',
  horizon: '20d',
  logic: 'and',
  conditions: [{ factor: 'main_inflow_1d', op: '>', value: 50_000_000 }],
};

const router = useRouter();

const name = ref('主力流入趋势');
const dsl = ref<Record<string, unknown>>({ ...DEFAULT_DSL });
// 编辑模式：非 null 时保存走 PATCH，标题提示正在编辑的策略名。
const editingId = ref<number | null>(null);
const strategies = ref<QuantStrategy[]>([]);
const factors = ref<QuantFactor[]>([]);
const preview = ref<{ errors: string[]; hit: boolean } | null>(null);
const error = ref<string | null>(null);
const saving = ref(false);

const sleeveOptions = Object.entries(SLEEVE_LABELS).map(([value, label]) => ({ value, label }));

async function load() {
  try {
    const response = await apiClient.getQuantStrategies();
    strategies.value = Array.isArray(response.data) ? response.data : [];
  } catch (err) {
    error.value = err instanceof Error ? err.message : '策略列表加载失败';
  }
}

async function loadFactors() {
  try {
    const response = await apiClient.getQuantFactors();
    factors.value = Array.isArray(response.data) ? response.data : [];
  } catch (err) {
    error.value = err instanceof Error ? err.message : '因子注册表加载失败';
  }
}

function startEdit(item: QuantStrategy) {
  editingId.value = item.id;
  name.value = item.name;
  dsl.value = { ...(item.dsl as Record<string, unknown>) };
  preview.value = null;
  error.value = null;
}

function cancelEdit() {
  editingId.value = null;
  name.value = '主力流入趋势';
  dsl.value = { ...DEFAULT_DSL };
  preview.value = null;
}

async function handlePreview() {
  try {
    const response = await apiClient.previewQuantStrategy({ name: name.value, dsl: dsl.value, is_active: false });
    preview.value = response.data;
    error.value = null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '预览失败';
  }
}

async function handleSave() {
  saving.value = true;
  try {
    if (editingId.value != null) {
      await apiClient.updateQuantStrategy(editingId.value, { name: name.value, dsl: dsl.value });
    } else {
      await apiClient.createQuantStrategy({ name: name.value, dsl: dsl.value, is_active: false });
    }
    await load();
    cancelEdit();
    error.value = null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败';
  } finally {
    saving.value = false;
  }
}

async function handleDelete(item: QuantStrategy) {
  if (!window.confirm(`删除策略「${item.name}」？此操作不可撤销。`)) return;
  try {
    await apiClient.deleteQuantStrategy(item.id);
    if (editingId.value === item.id) cancelEdit();
    await load();
    error.value = null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除失败';
  }
}

function handleBacktest(item: QuantStrategy) {
  void router.push({ path: '/desk/backtest', query: { strategy: String(item.id) } });
}

onMounted(() => {
  void load();
  void loadFactors();
});
</script>

<template>
  <div class="grid gap-4" data-role="desk-strategies-view">
    <header>
      <h1 class="page-title">策略工作台</h1>
      <p class="page-subtitle">条件组合器只能引用因子注册表；探索性策略默认不得晋级。</p>
    </header>
    <p v-if="error" class="text-sm text-danger">{{ error }}</p>
    <SectionCard eyebrow="Factors" title="因子注册表" subtitle="条件构建器的因子唯一来源，超出注册表会预览报错" data-role="desk-factor-registry">
      <table v-if="factors.length" class="w-full text-left text-sm">
        <thead class="text-muted">
          <tr>
            <th class="py-1 font-normal">因子键</th>
            <th class="py-1 font-normal">所属 Sleeve</th>
            <th class="py-1 font-normal">有效期限</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="factor in factors" :key="factor.key" class="text-text" data-role="desk-factor-row">
            <td class="py-1 font-mono text-xs">{{ factor.key }}</td>
            <td class="py-1">{{ sleeveLabel(factor.sleeve) }}</td>
            <td class="py-1">{{ factor.horizon }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-sm text-muted" data-role="desk-factor-registry-empty">因子注册表为空，或后端尚未接入。</p>
    </SectionCard>
    <SectionCard eyebrow="Builder" title="构建与预览" subtitle="选因子、定阈值；高级模式可直接编辑 JSON">
      <div class="flex flex-wrap items-center gap-3">
        <label class="grid gap-1 text-sm">
          <span class="text-muted">名称</span>
          <input v-model="name" class="rounded-md border border-border bg-panel px-3 py-1.5" data-role="desk-strategy-name" />
        </label>
        <span v-if="editingId != null" class="text-xs text-warning" data-role="desk-strategy-editing">
          编辑模式：修改后将覆盖原策略
        </span>
      </div>
      <div class="mt-3">
        <StrategyBuilder v-model="dsl" :factors="factors" />
      </div>
      <div class="mt-3 flex flex-wrap gap-2">
        <button type="button" class="rounded-md border border-border px-3 py-1.5 text-sm" data-role="desk-strategy-preview" @click="handlePreview">预览</button>
        <button
          type="button"
          class="rounded-md border px-3 py-1.5 text-sm"
          :class="editingId != null ? 'border-accent text-accent' : 'border-accent text-accent'"
          :disabled="saving"
          data-role="desk-strategy-save"
          @click="handleSave"
        >
          {{ saving ? '保存中…' : editingId != null ? '保存修改' : '保存为探索性策略' }}
        </button>
        <button v-if="editingId != null" type="button" class="rounded-md border border-border px-3 py-1.5 text-sm" data-role="desk-strategy-cancel-edit" @click="cancelEdit">
          取消编辑
        </button>
      </div>
      <p v-if="preview" class="mt-3 text-sm text-muted" data-role="desk-strategy-preview-result">
        {{ preview.errors.length ? `校验未通过：${preview.errors.join('、')}` : `校验通过 · 示例特征命中：${preview.hit ? '是' : '否'}` }}
      </p>
    </SectionCard>
    <SectionCard eyebrow="Saved" title="已保存策略" subtitle="探索性策略只做研究观察，不参与选票排名；可编辑、删除或一键送回测">
      <p v-if="!strategies.length" class="text-sm text-muted" data-role="desk-strategies-empty">
        尚无策略：默认探索性策略将在后端完成种子后自动出现，也可在上方构建后保存。
      </p>
      <ul v-else class="grid gap-2 text-sm" data-role="desk-strategy-list">
        <li
          v-for="item in strategies"
          :key="item.id"
          class="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
          data-role="desk-strategy-item"
        >
          <span>
            <span class="font-medium text-text">{{ item.name }}</span>
            <span class="text-muted"> · {{ item.exploratory ? '探索性' : '正式' }} · {{ item.is_active ? '观察中' : '未激活' }}</span>
          </span>
          <span class="flex flex-wrap gap-2">
            <button type="button" class="rounded-md border border-border px-2 py-1 text-xs text-text" data-role="desk-strategy-edit" @click="startEdit(item)">编辑</button>
            <button type="button" class="rounded-md border border-border px-2 py-1 text-xs text-accent" data-role="desk-strategy-backtest" @click="handleBacktest(item)">送回测</button>
            <button type="button" class="rounded-md border border-border px-2 py-1 text-xs text-danger" data-role="desk-strategy-delete" @click="handleDelete(item)">删除</button>
          </span>
        </li>
      </ul>
    </SectionCard>
  </div>
</template>
